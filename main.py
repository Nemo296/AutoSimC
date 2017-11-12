# -*- coding: utf-8 -*-
# pylint: disable=C0103
# pylint: disable=C0301

import configparser
import sys
import datetime
import os
import json
import shutil
import argparse
import logging
import itertools
import collections

from settings import settings

import specdata
import splitter
import hashlib

if __name__ == "__main__":
    try:
        filename = "settings.py"
        source = open(filename, 'r').read()
        compile(source, filename, 'exec')
    except SyntaxError:
        print("Error in settings.py, pls check for syntax-errors")
        sys.exit(1)

# Var init with default value
c_profileid = 0
c_profilemaxid = 0
legmin = int(settings.default_leg_min)
legmax = int(settings.default_leg_max)
t19min = int(settings.default_equip_t19_min)
t19max = int(settings.default_equip_t19_max)
t20min = int(settings.default_equip_t20_min)
t20max = int(settings.default_equip_t20_max)
t21min = int(settings.default_equip_t21_min)
t21max = int(settings.default_equip_t21_max)

outputFileName = settings.default_outputFileName
# txt, because standard-user cannot be trusted
inputFileName = settings.default_inputFileName

logFileName = settings.logFileName
errorFileName = settings.errorFileName
# quiet_mode for faster output; console is very slow
b_quiet = settings.b_quiet
i_generatedProfiles = 0

b_simcraft_enabled = settings.default_sim_enabled
s_stage = ""

iterations_firstpart = settings.default_iterations_stage1
iterations_secondpart = settings.default_iterations_stage2
iterations_thirdpart = settings.default_iterations_stage3

target_error_secondpart = settings.default_target_error_stage2
target_error_thirdpart = settings.default_target_error_stage3
gemspermutation = False

gem_ids = {}
gem_ids["150haste"] = "130220"
gem_ids["200haste"] = "151583"
gem_ids["haste"] = "151583"  # always contains maximum quality
gem_ids["150crit"] = "130219"
gem_ids["200crit"] = "151580"
gem_ids["crit"] = "151580"  # always contains maximum quality
gem_ids["150vers"] = "130221"
gem_ids["200vers"] = "151585"
gem_ids["vers"] = "151585"  # always contains maximum quality
gem_ids["150mast"] = "130222"
gem_ids["200mast"] = "151584"
gem_ids["mast"] = "151584"  # always contains maximum quality
gem_ids["200str"] = "130246"
gem_ids["str"] = "130246"
gem_ids["200agi"] = "130247"
gem_ids["agi"] = "130247"
gem_ids["200int"] = "130248"
gem_ids["int"] = "130248"


#   Error handle
def printLog(stringToPrint):
    logging.info(stringToPrint)


# Add legendary to the right tab
def addToTab(x):
    stringToAdd = "L,id=" + x[1] + (",bonus_id=" + x[2] if x[2] != "" else "") + (
        ",enchant_id=" + x[3] if x[3] != "" else "") + (",gem_id=" + x[4] if x[4] != "" else "")
    if x[0] == 'head':
        l_head.append(stringToAdd)
    elif x[0] == 'neck':
        l_neck.append(stringToAdd)
    elif x[0] == 'shoulders':
        l_shoulders.append(stringToAdd)
    elif x[0] == 'back':
        l_back.append(stringToAdd)
    elif x[0] == 'chest':
        l_chest.append(stringToAdd)
    elif x[0] == 'wrist':
        l_wrists.append(stringToAdd)
    elif x[0] == 'hands':
        l_hands.append(stringToAdd)
    elif x[0] == 'waist':
        l_waist.append(stringToAdd)
    elif x[0] == 'legs':
        l_legs.append(stringToAdd)
    elif x[0] == 'feet':
        l_feet.append(stringToAdd)
    elif x[0] == 'finger1':
        l_finger1.append(stringToAdd)
    elif x[0] == 'finger2':
        l_finger2.append(stringToAdd)
    elif x[0] == 'trinket1':
        l_trinket1.append(stringToAdd)
    elif x[0] == 'trinket2':
        l_trinket2.append(stringToAdd)


# Manage legendary with command line
def handlePermutation(elements):
    for element in elements:
        pieces = element.split('|')
        addToTab(pieces)


def build_gem_list(gems):
    splitted_gems = gems.split(",")
    for gem in splitted_gems:
        if gem not in gem_ids.keys():
            raise ValueError("Unknown gem '{}' to sim, please check your input. Valid gems: {}".
                             format(gem, gem_ids.keys()))
    # Convert parsed gems to list of gem ids
    return [gem_ids[gem] for gem in splitted_gems]


def cleanItem(item_string):
    if "--" in item_string:
        item_string = item_string.split("--")[1]

    return item_string


# Check if permutation is valid
antorusTrinkets = {"154172", "154173", "154174", "154175", "154176", "154177"}


itemIDsMemoization = {}


def getIdFromItem(item):
    # Since items aren't object with an itemID property, we do some memoization here
    if item in itemIDsMemoization:
        return itemIDsMemoization[item]
    else:
        splits = item.split(",")
        for s in splits:
            if s.startswith("id="):
                itemIDsMemoization[item] = s[3:]
                return itemIDsMemoization[item]


def parse_command_line_args():
    """Parse command line arguments using argparse. Also provides --help functionality, and default values for args"""

    parser = argparse.ArgumentParser(description="Python script to create multiple profiles for SimulationCraft to "
                                     "find Best-in-Slot and best enchants/gems/talents combinations.",
                                     epilog="Don't hesitate to go on the SimcMinMax Discord "
                                     "(https://discordapp.com/invite/tFR2uvK) "
                                     "in the #simpermut-autosimc Channel to ask about specific stuff.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter  # Show default arguments
                                     )

    parser.add_argument('-i', '--inputfile',
                        default="input.txt",
                        required=False,
                        help="Inputfile describing the permutation of SimC profiles to generate. See README for more "
                        "details.")

    parser.add_argument('-o', '--outputfile',
                        default="out.simc",
                        required=False,
                        help='Output file containing the generated profiles used for the simulation.')

    parser.add_argument('-sim',
                        required=False,
                        nargs="*",
                        choices=['stage1', 'stage2', 'stage3'],
                        help="Enables automated simulation and ranking for the top 3 dps-gear-combinations. "
                        "Might take a long time, depending on number of permutations. "
                        "Edit the simcraft-path in settings.py to point to your simc-installation. The result.html "
                        "will be saved in results-subfolder."
                        "There are 2 modes available for calculating the possible huge amount of permutations: "
                        "Static and dynamic mode:"
                        "* Static uses a fixed amount of simc-iterations at the cost of quality; default-settings are "
                        "100, 1000 and 10000 for each stage."
                        "* Dynamic mode lets you set the target_error-parameter from simc, resulting in a more "
                        "accurate ranking. Stage 1 can be entered at the beginning in the wizard. Stage 2 is set to "
                        "target_error=0.2, and 0.05 for the final stage 3."
                        "(These numbers might be changed in future versions)"
                        "You have to set the simc path in the settings.py file."
                        "- Resuming: It is also possible to resume a broken stage, e.g. if simc.exe crashed during "
                        "stage1, by launching with the parameter -sim stage2 (or stage3). You will have to enter the "
                        "amount of iterations or target_error of the broken simulation-stage. (See logs.txt for details)"
                        "- Parallel Processing: By default multiple simc-instances are launched for stage1 and 2, "
                        "which is a major speedup on modern multicore-cpus like AMD Ryzen. If you encounter problems "
                        "or instabilities, edit settings.py and change the corresponding parameters or even disable it. "
                        )

    parser.add_argument('-quiet', '--quiet',
                        action='store_true',
                        help='Option for disabling Console-output. Generates the outputfile much faster for '
                        'large permuation-size')

    parser.add_argument('-gems', '--gems',
                        required=False,
                        help='Enables permutation of gem-combinations in your gear. With e.g. gems crit,haste,int '
                        'you can add all combinations of the corresponding gems (epic gems: 200, rare: 150, uncommon '
                        'greens are not supported) in addition to the ones you have currently equipped.\n'
                        'Valid gems: {}'
                        '- Example: You have equipped 1 int and 2 mastery-gems. If you enter <-gems "crit,haste,int"> '
                        '(without <>) into the commandline, the permutation process uses the single int- '
                        'and mastery-gem-combination you have currrently equipped and adds ALL combinations from the '
                        'ones in the commandline, therefore mastery would be excluded. However, adding mastery to the '
                        'commandline reenables that.\n'
                        '- Gems have to fulfil the following syntax in your profile: gem_id=123456[[/234567]/345678] '
                        'Simpermut usually creates this for you.\n'
                        '- WARNING: If you have many items with sockets and/or use a vast gem-combination-setup as '
                        'command, the number of combinations will go through the roof VERY quickly. Please be cautious '
                        'when enabling this.'.format(list(gem_ids.keys())))

    parser.add_argument('-l', '--legendaries',
                        required=False,
                        help='List of legendaries to add to the template. Format:\n'
                        '"leg1/id/bonus/gem/enchant,leg2/id2/bonus2/gem2/enchant2,..."')

    parser.add_argument('-Min_leg', '--legendary_min',
                        default=0,
                        type=int,
                        required=False,
                        help='Minimum number of legendaries in the permutations.')

    parser.add_argument('-max_leg', '--legendary_max',
                        default=2,
                        type=int,
                        required=False,
                        help='Maximum number of legendaries in the permutations.')

    parser.add_argument('--debug',
                        action='store_true',
                        help='Write debug information to log file.')

    return parser.parse_args()


# Manage command line parameters
# todo: include logic to split into smaller/larger files (default 50)
def handleCommandLine():
    args = parse_command_line_args()
    logging.debug("Parsed command line arguments: {}".format(args))

    # For now, just write command line arguments into globals
    global inputFileName
    global outputFileName
    global legmin
    global legmax
    global b_quiet
    global b_simcraft_enabled
    global s_stage
    global restart
    global gemspermutation
    inputFileName = args.inputfile
    outputFileName = args.outputfile
    legmin = args.legendary_min
    legmax = args.legendary_max
    b_quiet = args.quiet

    # Sim Argument is either None when not specified, a empty list [] when specified without an argument,
    # or a list with one
    # argument, eg. ["stage1"]
    b_simcraft_enabled = (args.sim is not None)
    if args.sim is not None and len(args.sim) > 0:
        s_stage = args.sim[0]

    # Check simc executable availability. Maybe move to somewhere else.
    if b_simcraft_enabled:
        if not os.path.exists(settings.simc_path):
            printLog("Error: Wrong path to simc.exe: " + str(settings.simc_path))
            print("Error: Wrong path to simc.exe: " + str(settings.simc_path))
            sys.exit(1)
        else:
            printLog("Path to simc.exe valid, proceeding...")

    gemspermutation = args.gems
    if args.legendaries is not None:
        handlePermutation(args.legendaries.split(','))
    if args.gems is not None:
        global splitted_gems
        splitted_gems = build_gem_list(args.gems)

    return args


# returns target_error, iterations, elapsed_time_seconds for a given class_spec
def get_data(class_spec):
    result = []
    f = open(os.path.join(os.getcwd(), settings.analyzer_path, settings.analyzer_filename), "r")
    file = json.load(f)
    for variant in file[0]:
        for p in variant["playerdata"]:
            if p["specialization"] == class_spec:
                for s in range(len(p["specdata"])):
                    item = (
                        variant["target_error"], p["specdata"][s]["iterations"],
                        p["specdata"][s]["elapsed_time_seconds"])
                    result.append(item)
    return result


def cleanup():
    printLog("Cleaning up")
    result_folder = os.path.join(os.getcwd(), settings.result_subfolder)
    if not os.path.exists(result_folder):
        logging.info("Result-subfolder '{}' does not exist. Creating it.".format(result_folder))
        os.makedirs(result_folder)

    subdir3 = os.path.join(os.getcwd(), settings.subdir3)
    if os.path.exists(subdir3):
        for _root, _dirs, files in os.walk(subdir3):
            for file in files:
                if file.endswith(".html"):
                    printLog("Moving file: " + str(file))
                    shutil.move(os.path.join(os.getcwd(), settings.subdir3, file),
                                os.path.join(os.getcwd(), settings.result_subfolder, file))

    subdir1 = os.path.join(os.getcwd(), settings.subdir1)
    if os.path.exists(subdir1):
        if settings.delete_temp_default or input("Do you want to remove subfolder: " + subdir1 + "? (Press y to confirm): ") == "y":
            printLog("Removing: {}".format(subdir1))
            shutil.rmtree(subdir1)

    subdir2 = os.path.join(os.getcwd(), settings.subdir2)
    if os.path.exists(subdir2):
        if settings.delete_temp_default or input("Do you want to remove subfolder: " + subdir2 + "? (Press y to confirm): ") == "y":
            shutil.rmtree(subdir2)
            printLog("Removing: " + subdir2)

    subdir3 = os.path.join(os.getcwd(), settings.subdir3)
    if os.path.exists(subdir3):
        if settings.delete_temp_default or input("Do you want to remove subfolder: " + subdir3 + "? (Press y to confirm): ") == "y":
            shutil.rmtree(subdir3)
            printLog("Removing: " + subdir3)


def validateSettings():
    # validate amount of legendaries
    if legmin > legmax:
        raise ValueError("Legendary min '{}' > legendary max '{}'".format(legmin, legmax))
    if legmax > 3:
        raise ValueError("Legendary Max '{}' too large (>3).".format(legmax))
    if legmin > 3:
        raise ValueError("Legendary Min '{}' too large (>3).".format(legmin))
    if legmin < 0:
        raise ValueError("Legendary Min '{}' is negative.".format(legmin))
    if legmax < 0:
        raise ValueError("Legendary Max '{}' is negative.".format(legmax))

    # validate tier-set
    min_tier_sets = 0
    max_tier_sets = 6
    tier_sets = {"Tier19": (t19min, t19max),
                 "Tier20": (t20min, t20max),
                 "Tier21": (t21min, t21max),
                 }

    total_min = 0
    for tier_name, (tier_set_min, tier_set_max) in tier_sets.items():
        if tier_set_min < min_tier_sets:
            raise ValueError("Invalid tier set minimum ({} < {}) for tier '{}'".
                             format(tier_set_min, min_tier_sets, tier_name))
        if tier_set_max > max_tier_sets:
            raise ValueError("Invalid tier set maximum ({} > {}) for tier '{}'".
                             format(tier_set_max, max_tier_sets, tier_name))
        if tier_set_min > tier_set_max:
            raise ValueError("Tier set min > max ({} > {}) for tier '{}'".format(tier_set_min, tier_set_max, tier_name))
        total_min += tier_set_min

    if total_min > max_tier_sets:
        raise ValueError("All tier sets together have too much combined min sets ({}=sum({}) > {}).".
                         format(total_min, [t[0] for t in tier_sets.values()], max_tier_sets))

    # use a "safe mode", overwriting the values
    if settings.simc_safe_mode:
        printLog("Using Safe Mode")
        settings.simc_threads = 1
    if b_simcraft_enabled:
        if os.name == "nt":
            if not settings.simc_path.endswith("simc.exe"):
                raise RuntimeError("simc.exe wrong or missing in settings.py path-variable, please edit it")

        analyzer_path = os.path.join(os.getcwd(), settings.analyzer_path, settings.analyzer_filename)
        if os.path.exists(analyzer_path):
            logging.info("Analyzer-file found at '{}'.".format(analyzer_path))
        else:
            raise RuntimeError("Analyzer-file not found at '{}', make sure you have a complete AutoSimc-Package.".
                               format(analyzer_path))

    if settings.default_error_rate_multiplier <= 0:
        raise ValueError("Invalid default_error_rate_multiplier ({}) <= 0".
                         format(settings.default_error_rate_multiplier))


def file_checksum(filename):
    hash_md5 = hashlib.sha3_256()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_Possible_Gem_Combinations(gems_to_use, numberOfGems):
    if numberOfGems <= 0:
        return []
    printLog("Creating Gem Combinations")
    printLog("Number of Gems: " + str(numberOfGems))
    combinations = itertools.combinations_with_replacement(gems_to_use, r=numberOfGems)
    combinations = ["/".join(c) for c in combinations]
    return combinations


gemIDsMemoization = {}


def getGemsFromItem(item):
    # Since items aren't object with an itemID property, we do some memoization here
    if item in gemIDsMemoization:
        return gemIDsMemoization[item]
    else:
        a = item.split(",")
        gems = []
        for i in range(len(a)):
            # look for gem_id-string in items
            if a[i].startswith("gem_id"):
                _b, c = a[i].split("=")
                gems = c.split("/")
                # up to 3 possible gems
        gemIDsMemoization[item] = gems
        return gems


# gearlist contains a list of items, as in l_head
def permutateGemsInSlotGearList(slot_gearlist):
    for item in slot_gearlist:
        logging.debug("Permutating slot_item: {}".format(item))
        item_attributes = item.split(",")
        gems = []
        for attr in item_attributes:
            # look for gem_id-string in items
            if attr.startswith("gem_id"):
                _name, ids = attr.split("=")
                logging.debug("Existing gems: {}".format(ids))
                gems = ids.split("/")
                break
        num_gems = len(gems)
        if num_gems == 0:
            logging.debug("No gems to permutate")
            continue

        new_gems = get_Possible_Gem_Combinations(splitted_gems, num_gems)
        # logging.debug("New Gems: {}".format(new_gems))
        new_item = ""
        for attr in item_attributes:
            if not str(attr).startswith("gem") and not attr == "":
                new_item += "," + str(attr)
        for gem in new_gems:
            ins = new_item + ",gem_id=" + gem
            if ins not in slot_gearlist:
                slot_gearlist.insert(0, ins)

            # look for gems-string in items
            # todo implement
            if attr.startswith("gems"):
                print(str(attr))
    logging.debug("Final slot list: {}".format(slot_gearlist))


def permutateGems(slot_name, slot):
    logging.debug("Permutating Gems for slot {}".format(slot_name))
    permutateGemsInSlotGearList(slot)


def permutate_talents(talents):
    # First create a list where each entry represents all the talent permutations in that row.
    talent_combinations = []
    for i, talent in enumerate(talents[0]):
        if settings.permutate_row[i]:
            # We permutate the talent row, adding ['1', '2', '3'] to that row
            talent_combinations.append([str(x) for x in range(1, 4)])
        else:
            # Do not permutate the talent row, just add the talent from the profile
            talent_combinations.append([talent])
    logging.debug("Talent combination input: {}".format(talent_combinations))

    # Use some itertools magic to unpack the product of all talent combinations
    product = itertools.product(*talent_combinations)

    # Format each permutation back to a nice talent string.
    permuted_talent_strings = ["".join(s) for s in product]
    logging.debug("Talent combinations: {}".format(permuted_talent_strings))
    return permuted_talent_strings


def print_permutation_progress(current, maximum):
    # output status every 5000 permutations, user should get at least a minor progress shown; also does not slow down
    # computation very much
    if current % 5000 == 0:
        logging.info("Processed {}/{} ({:.2f}%)".format(current,
                                                        maximum,
                                                        100.0 * current / maximum))
    if current == maximum:
        logging.info("Processed: {}/{} ({:.2f}%)".format(current,
                                                         max,
                                                         100.0 * current / maximum))


class Profile:
    """Represent global profile data"""
    pass


class PermutationData:
    """Data for each permutation"""
    def __init__(self, permutation_data, to_permutate, profile):
        self.profile = profile
        self.combined_data = {}
        for j, entry in enumerate(to_permutate):
            entry = list(entry)
            self.combined_data.update({key: permutation_data[j][i] for i, key in enumerate(entry)})
        self.not_usable = self.check_usable()

    def check_usable(self):
        """Check if profile is un-usable. Return None if ok, otherwise return reason"""
        self.nbLeg = 0
        self.temp_t19 = 0
        self.temp_t20 = 0
        self.temp_t21 = 0
        for gear in self.combined_data.values():
            if len(gear) and gear[0] == "L":
                nbLeg = self.nbLeg + 1
                continue
            gearLabel = gear[0:3]
            if gearLabel == "T19":
                self.temp_t19 = self.temp_t19 + 1
                continue
            if gearLabel == "T20":
                self.temp_t20 = self.temp_t20 + 1
                continue
            if gearLabel == "T21":
                self.temp_t21 = self.temp_t21 + 1

        if self.nbLeg < legmin:
            return str(nbLeg) + " leg (" + str(legmin) + " asked)"
        if self.nbLeg > legmax:
            return str(nbLeg) + " leg (" + str(legmax) + " asked)"
        # check if amanthuls-trinket is the 3rd trinket; otherwise its an invalid profile
        # because 3 other legs have been equipped
        if self.nbLeg == 3:
            if not getIdFromItem(self.combined_data["trinket1"]) == "154172" and not getIdFromItem(self.combined_data["trinket2"]) == "154172":
                return " 3 legs equipped, but no Amanthul-Trinket found"

        if self.temp_t19 < t19min:
            return " " + str(self.temp_t19) + ": too few T19-items (" + str(t19min) + " asked)"
        if self.temp_t20 < t20min:
            return " " + str(self.temp_t20) + ": too few T20-items (" + str(t20min) + " asked)"
        if self.temp_t21 < t21min:
            return " " + str(self.temp_t21) + ": too few T21-items (" + str(t21min) + " asked)"
        if self.temp_t19 > t19max:
            return " " + str(self.temp_t19) + ": too much T19-items (" + str(t19max) + " asked)"
        if self.temp_t20 > t20max:
            return " " + str(self.temp_t20) + ": too much T20-items (" + str(t20max) + " asked)"
        if self.temp_t21 > t21max:
            return " " + str(self.temp_t21) + ": too much T21-items (" + str(t21max) + " asked)"

        if getIdFromItem(self.combined_data["finger1"]) == getIdFromItem(self.combined_data["finger2"]):
            return "Rings equal"

        trinket1itemID = getIdFromItem(self.combined_data["trinket1"])
        trinket2itemID = getIdFromItem(self.combined_data["trinket2"])

        if trinket1itemID == trinket2itemID:
            return "trinkets equal"

        if trinket1itemID in antorusTrinkets:
            if trinket2itemID in antorusTrinkets:
                return " two Pantheon-Trinkets found"
        return None

    def get_profile_name(self, valid_profile_number):
        # namingdata contains info for the profile-name
        namingData = {}
        # if a valid profile was detected, fill namingData; otherwise its pointless
        if self.nbLeg == 0:
            namingData['Leg0'] = ""
            namingData["Leg1"] = ""
        elif self.nbLeg == 1:
            for gear in self.combined_data.values():
                if len(gear) > 0 and gear[0] == "L":
                    namingData['Leg0'] = getIdFromItem(gear[0])
        elif self.nbLeg == 2:
            for gear in self.combined_data.values():
                if len(gear) > 0 and gear[0] == "L":
                    if namingData.get('Leg0') is not None:
                        namingData['Leg1'] = getIdFromItem(gear)
                    else:
                        namingData['Leg0'] = getIdFromItem(gear)
        elif self.nbLeg == 3:
            for gear in self.combined_data.values():
                if len(gear) > 0 and gear[0] == "L":
                    if namingData.get('Leg0') is None:
                        namingData['Leg0'] = getIdFromItem(gear)
                    else:
                        if namingData.get('Leg1') is not None:
                            namingData['Leg1'] = getIdFromItem(gear)
                        else:
                            namingData['Leg2'] = getIdFromItem(gear)

        namingData["T19"] = self.temp_t19
        namingData["T20"] = self.temp_t20
        namingData["T21"] = self.temp_t21

        # example: "Uther_Soul_T19-2p_T20-2p_T21-2p"
        # scpout later adds a increment for multiple versions of this
        template = "%A%B%C%D%E%F"
        if namingData.get('Leg0') != "None":
            template = template.replace("%A", str(specdata.getAcronymForID(namingData.get('Leg0'))) + "_")
        else:
            template = template.replace("%A", "")

        if namingData.get('Leg1') != "None":
            template = template.replace("%B", str(specdata.getAcronymForID(namingData.get('Leg1'))) + "_")
        else:
            template = template.replace("%B", "")

        if namingData.get('Leg2') != "None":
            template = template.replace("%C", str(specdata.getAcronymForID(namingData.get('Leg2'))) + "_")
        else:
            template = template.replace("%C", "")

        if namingData.get("T19") != "None" and namingData.get("T19") != 0 and namingData.get(
                "T19") != 1 and namingData.get("T19") != 3 and namingData.get("T19") != 5:
            template = template.replace("%D", "T19-" + str(namingData.get('T19')) + "p_")
        else:
            template = template.replace("%D", "")

        if namingData.get("T20") != "None" and namingData.get("T20") != 0 and namingData.get(
                "T20") != 1 and namingData.get("T20") != 3 and namingData.get("T20") != 5:
            template = template.replace("%E", "T20-" + str(namingData.get('T20')) + "p_")
        else:
            template = template.replace("%E", "")

        if namingData.get("T21") != "None" and namingData.get("T21") != 0 and namingData.get(
                "T21") != 1 and namingData.get("T21") != 3 and namingData.get("T21") != 5:
            template = template.replace("%F", "T21-" + str(namingData.get('T21')) + "p_")
        else:
            template = template.replace("%F", "")

        return "_".join((template, str(valid_profile_number)))

    def get_profile(self):
        return "\n".join(["{}={}".format(key, value) for key, value in self.combined_data.items()])

    def write_to_file(self, filehandler, valid_profile_number):
        profile_name = self.get_profile_name(valid_profile_number)
        filehandler.write("{}={}\n".format(self.profile.wow_class, profile_name))
        combined_profile = "\n".join((self.profile.general_options, self.get_profile()))
        filehandler.write(combined_profile)
        filehandler.write("\n\n")


# todo: add checks for missing headers, prio low
def permutate():
    # Read input.txt to init vars
    config = configparser.ConfigParser()

    # use read_file to get a error when input file is not available
    with open(inputFileName, encoding='utf-8-sig') as f:
        config.read_file(f)

    profile = config['Profile']
    gear = config['Gear']

    if 'class' in profile:
        raise RuntimeError("You input class format is wrong, please update SimPermut or your input file.")

    # Read input.txt
    #   Profile
    valid_classes = ["priest",
                     "druid",
                     "warrior",
                     "paladin",
                     "hunter",
                     "deathknight",
                     "demonhunter",
                     "mage",
                     "monk",
                     "rogue",
                     "shaman",
                     "warlock",
                     ]
    for wow_class in valid_classes:
        if config.has_option('Profile', wow_class):
            c_class = wow_class
            c_profilename = profile[wow_class]
            break
    else:
        raise RuntimeError("No valid wow class found in Profile section of input file. Valid classes are: {}".
                           format(valid_classes))
    player_profile = Profile()
    player_profile.simc_options = {}
    player_profile.wow_class = c_class
    player_profile.profile_name = c_profilename

    # Parse general profile options
    simc_profile_options = ["race",
                            "level",
                            "spec",
                            "role",
                            "position",
                            "artifacts",
                            "crucible",
                            "potion",
                            "flask",
                            "food",
                            "augmentation"]
    for opt in simc_profile_options:
        if opt in profile:
            player_profile.simc_options[opt] = profile[opt]

    player_profile.class_spec = specdata.getClassSpec(c_class, player_profile.simc_options["spec"])
    player_profile.class_role = specdata.getRole(c_class, player_profile.simc_options["spec"])

    # Build 'general' profile options which do not permutate once into a simc-string
    logging.info("SimC options: {}".format(player_profile.simc_options))
    player_profile.general_options = "\n".join(["{}={}".format(key, value) for key, value in
                                                player_profile.simc_options.items()])
    logging.debug("Built simc general options string: {}".format(player_profile.general_options))

    # Items to parse
    gear_slots = ["head",
                  "neck",
                  "shoulder",
                  "back",
                  "chest",
                  "wrist",
                  "hands",
                  "waist",
                  "legs",
                  "feet",
                  "finger1",
                  "finger2",
                  "trinket1",
                  "trinket2",
                  "main_hand",
                  "off_hand"]
    parsed_gear = {}
    for gear_slot in gear_slots:
        parsed_gear[gear_slot] = gear.get(gear_slot, "").split("|")

    logging.info("Parsed gear: {}".format(parsed_gear))

    # Split vars to lists
    l_talents = profile.get("talents", "").split('|')

    # This represents a dict of all options which will be permutated fully with itertools.product
    normal_permutation_options = collections.OrderedDict({})

    # Add talents to permutations
    if settings.enable_talent_permutation:
        normal_permutation_options["talents"] = permutate_talents(l_talents)

    # add gem-permutations to gear
    if gemspermutation:
        for name, gear in parsed_gear.items():
            permutateGems(name, gear)

    # Add 'normal' gear to normal permutations, excluding trinket/rings
    gear_normal = {k: v for k, v in parsed_gear.items() if (not k.startswith("finger") and not k.startswith("trinket"))}
    normal_permutation_options.update(gear_normal)

    # Calculate normal permutations
    normal_permutations = itertools.product(*normal_permutation_options.values())

    special_permutations_config = {"finger": ("finger1", "finger2"),
                                   "trinket": ("trinket1", "trinket2")
                                   }
    special_permutations = []
    for name, values in special_permutations_config.items():
        # Get entries from parsed gear, exclude empty finger/trinket lines
        entries = [v for k, v in parsed_gear.items() if k.startswith(name)]
        entries = list(itertools.chain(*entries))
        entries = [e for e in entries if len(e)]  # Filter empty finger/trinket input lines
        logging.debug("Input list for special permutation '{}': {}".format(name,
                                                                           entries))
        if 1:  # Unique finger/trinkets. This might be exposed as an option later
            # This will not completly avoid 2 same ring ids equipped, but at least not two exactly equal
            # ring strings.
            permutations = itertools.combinations(entries, len(values))
        else:
            permutations = itertools.combinations_with_replacement(entries, len(values))
        permutations = list(permutations)
        logging.info("Got {} permutations for {}.".format(len(permutations),
                                                          name))
        logging.debug(permutations)

        entry_dict = {v: None for v in values}
        special_permutations.append((name, entry_dict, permutations))

    # Set up the combined permutation list with normal + special permutations
    all_permutation_options = [normal_permutations, *[opt for _name, _entries, opt in special_permutations]]
    all_permutations = itertools.product(*all_permutation_options)
    special_names = [list(entries.keys()) for _name, entries, _opt in special_permutations]
    all_permutation_names = [list(normal_permutation_options.keys()), *special_names]

    # Calculate & Display number of permutations
    max_num_profiles = 1
    for name, perm in normal_permutation_options.items():
        max_num_profiles *= len(perm)
    permutations_product = {"normal gear&talents":  "{} ({})".format(max_num_profiles,
                                                                     {name: len(items) for name, items in
                                                                      normal_permutation_options.items()}
                                                                     )
                            }
    for name, _entries, opt in special_permutations:
        max_num_profiles *= len(opt)
        permutations_product[name] = len(opt)
    logging.info("Max number of profiles: {}".format(max_num_profiles))
    logging.info("Number of permutations: {}".format(permutations_product))

    # Start the permutation!
    processed = 0
    valid_profiles = 0
    with open(outputFileName, 'w') as output_file:
        for perm in all_permutations:
            data = PermutationData(perm, all_permutation_names, player_profile)
            if not data.not_usable:
                data.write_to_file(output_file, valid_profiles)
                valid_profiles += 1
            print_permutation_progress(processed, max_num_profiles)
            processed += 1

    logging.info("Ending permutations. Valid: {:n} of {:n} processed. ({:.2f}%)".
                 format(valid_profiles,
                        processed,
                        100.0 * valid_profiles / max_num_profiles if max_num_profiles else 0.0))

    # Print checksum so we can check for equality when making changes in the code
    outfile_checksum = file_checksum(outputFileName)
    logging.info("Output file checksum: {}".format(outfile_checksum))

    global i_generatedProfiles
    i_generatedProfiles = valid_profiles

    return player_profile


def checkResultFiles(subdir, player_profile, count = 2):
    subdir = os.path.join(os.getcwd(), subdir)
    printLog("Checking Files in subdirectory: {}".format(subdir))
    if os.path.exists(subdir):
        empty = 0
        checkedFiles = 0
        for _root, _dirs, files in os.walk(subdir):
            for file in files:
                checkedFiles += 1
                if file.endswith(".result"):
                    filename = os.path.join(subdir, file)
                    if os.stat(filename).st_size <= 0:
                        printLog("File is empty: {}".format(file))
                        empty += 1
    else:
        printLog("Error: Subdir does not exist: {}".format(subdir))
        return False

    if checkedFiles == 0:
        printLog("No files in: " + str(subdir))
        print("No files in: " + str(subdir) + ", exiting")
        return False

    if empty > 0:
        printLog("Empty files in: " + str(subdir) + " -> " + str(empty))
        print("Warning: Empty files in: " + str(subdir) + " -> " + str(empty))

        if not settings.skip_questions:
            q = input("Do you want to resim the empty files? Warning: May not succeed! (Press q to quit): ")
            if q == "q":
                printLog("User exit")
                sys.exit(0)

        printLog(F"Resimming files: Count: {count}")
        if count > 0:
            count -= 1
            if splitter.resim(subdir, player_profile):
                return checkResultFiles(subdir)
        else:
            printLog("Maximum number of retries reached, sth. is wrong; exiting")
            sys.exit(0)
    else:
        printLog("Checked all files in " + str(subdir) + " : Everything seems to be alright.")
        print("Checked all files in " + str(subdir) + " : Everything seems to be alright.")
        return True


def static_stage1(player_profile):
    printLog("Entering static mode, stage1")
    # split into chunks of 50
    splitter.split(outputFileName, settings.splitting_size)
    # sim these with few iterations, can still take hours with huge permutation-sets; fewer than 100 is not advised
    splitter.sim(settings.subdir1, "iterations=" + str(iterations_firstpart), player_profile, 1)
    static_stage2(player_profile)


def static_stage2(player_profile):
    printLog("Entering static mode, stage2")
    if checkResultFiles(settings.subdir1, player_profile):
        # now grab the top 100 of these and put the profiles into the 2nd temp_dir
        splitter.grabBest(settings.default_top_n_stage2, settings.subdir1, settings.subdir2, outputFileName)
        # where they are simmed again, now with 1000 iterations
        splitter.sim(settings.subdir2, "iterations=" + str(iterations_secondpart), player_profile, 1)
    else:
        printLog("Error, some result-files are empty in " + str(settings.subdir1))
        print("Error, some result-files are empty in " + str(settings.subdir1))
        sys.exit(1)
    static_stage3(player_profile)


def static_stage3(player_profile):
    printLog("Entering static mode, stage3")
    if checkResultFiles(settings.subdir2, player_profile):
        # again, for a third time, get top 3 profiles and put them into subdir3
        splitter.grabBest(settings.default_top_n_stage3, settings.subdir2, settings.subdir3, outputFileName)
        # sim them finally with all options enabled; html-output remains in this folder
        splitter.sim(settings.subdir3, "iterations=" + str(iterations_thirdpart), player_profile, 2)
    else:
        printLog("Error, some result-files are empty in " + str(settings.subdir1))
        print("Error, some result-files are empty in " + str(settings.subdir1))
        sys.exit(1)
    print("Simulation succeed!")


def dynamic_stage1(player_profile):
    printLog("Entering dynamic mode, stage1")
    result_data = get_data(class_spec)
    print("Listing options:")
    print("Estimated calculation times based on your data:")
    print("Class/Spec: " + str(class_spec))
    print("Number of permutations to simulate: " + str(i_generatedProfiles))
    for current in range(len(result_data)):
        te = result_data[current][0]
        tp = round(float(result_data[current][2]), 2)
        est = round(float(result_data[current][2]) * i_generatedProfiles, 0)
        h = round(est / 3600, 1)

        print("(" + str(current) + "): Target Error: " + str(te) + "%: " + " Time/Profile: " + str(
            tp) + " sec => Est. calc. time: " + str(est) + " sec (~" + str(h) + " hours)")

    if settings.skip_questions:
        calc_choice = settings.auto_dynamic_stage1_target_error_table
    else:
        calc_choice = input("Please enter the type of calculation to perform (q to quit): ")
    if calc_choice == "q":
        printLog("Quitting application")
        sys.exit(0)
    if int(calc_choice) < len(result_data) and int(calc_choice) >= 0:
        printLog("Sim: Chosen Class/Spec: " + str(class_spec))
        printLog("Sim: Number of permutations: " + str(i_generatedProfiles))
        printLog("Sim: Chosen calculation:" + str(int(calc_choice)))

        te = result_data[int(calc_choice)][0]
        print("selected target error: {}".format(te))
        tp = round(float(result_data[int(calc_choice)][2]), 2)
        est = round(float(result_data[int(calc_choice)][2]) * i_generatedProfiles, 0)

        printLog(
            "Sim: (" + str(calc_choice) + "): Target Error: " + str(te) + "%:" + " Time/Profile: " + str(
                tp) + " => Est. calc. time: " + str(est) + " sec")
        time_all = round(est, 0)
        printLog("Estimated calculation time: " + str(time_all) + "")
        if not settings.skip_questions:
            if time_all > 43200:
                if input("Warning: This might take a *VERY* long time (>12h) (q to quit, Enter to continue: )") == "q":
                    print("Quitting application")
                    sys.exit(0)

        # split into chunks of n (max 100) to not destroy the hdd
        # todo: calculate dynamic amount of n
        splitter.split(outputFileName, settings.splitting_size)
        splitter.sim(settings.subdir1, "target_error=" + str(te), player_profile, 1)

        # if the user chose a target_error which is lower than the default_one for the next step
        # he is given an option to either skip stage 2 or adjust the target_error
        if float(te) <= float(settings.default_target_error_stage2):
            printLog("Target_Error chosen in stage 1: " + str(te) + " <= Default_Target_Error for stage 2: " + str(
                settings.default_target_error_stage2) + "\n")
            print("Warning!\n")
            print("Target_Error chosen in stage 1: " + str(te) + " <= Default_Target_Error for stage 2: " + str(
                settings.default_target_error_stage2) + "\n")
            new_value = input(
                "Do you want to continue anyway (y), quit (q), skip to stage3 (s) or enter a new target_error"
                " for stage2 (n)?: ")
            printLog("User chose: " + str(new_value))
            if new_value == "q":
                sys.exit(0)
            if new_value == "n":
                target_error_secondpart = input("Enter new target_error (Format: 0.3): ")
                printLog("User entered target_error_secondpart: " + str(target_error_secondpart))
                dynamic_stage2(target_error_secondpart, str(te), player_profile)
            if new_value == "s":
                dynamic_stage3(True, settings.default_target_error_stage3, str(te))
            if new_value == "y":
                dynamic_stage2(settings.default_target_error_stage2, str(te), player_profile)
        else:
            pass
            dynamic_stage2(settings.default_target_error_stage2, str(te), player_profile)


def dynamic_stage2(targeterror, targeterrorstage1, player_profile):
    printLog("Entering dynamic mode, stage2")
    checkResultFiles(settings.subdir1, player_profile)
    if settings.default_use_alternate_grabbing_method:
        splitter.grabBestAlternate(targeterrorstage1, settings.subdir1, settings.subdir2, outputFileName)
    else:
        # grabbing top 100 files
        splitter.grabBest(settings.default_top_n_stage2, settings.subdir1, settings.subdir2, outputFileName)
    # where they are simmed again, now with higher quality
    splitter.sim(settings.subdir2, "target_error=" + str(targeterror), player_profile, 1)
    # if the user chose a target_error which is lower than the default_one for the next step
    # he is given an option to either skip stage 2 or adjust the target_error
    if float(target_error_secondpart) <= float(settings.default_target_error_stage3):
        printLog("Target_Error chosen in stage 2: " + str(
            targeterror) + " <= Default_Target_Error stage 3: " + str(
            settings.default_target_error_stage3))
        print("Warning!\n")
        printLog("Target_Error chosen in stage 2: " + str(
            targeterror) + " <= Default_Target_Error stage 3: " + str(
            settings.default_target_error_stage3))
        new_value = input(
            "Do you want to continue (y), quit (q) or enter a new target_error for stage3 (n)?: ")
        printLog("User chose: " + str(new_value))
        if new_value == "q":
            sys.exit(0)
        if new_value == "n":
            target_error_thirdpart = input("Enter new target_error (Format: 0.3): ")
            printLog("User entered target_error_thirdpart: " + str(target_error_thirdpart))
            dynamic_stage3(False, target_error_thirdpart, targeterror, player_profile)
        if new_value == "y":
            dynamic_stage3(False, settings.default_target_error_stage3, targeterror, player_profile)
    else:
        dynamic_stage3(False, settings.default_target_error_stage3, targeterror, player_profile)


def dynamic_stage3(skipped, targeterror, targeterrorstage2, player_profile):
    printLog("Entering dynamic mode, stage3")
    ok = False
    if skipped:
        ok = checkResultFiles(settings.subdir1, player_profile)
    else:
        ok = checkResultFiles(settings.subdir2, player_profile)
    if ok:
        printLog(".result-files ok, proceeding")
        # again, for a third time, get top 3 profiles and put them into subdir3
        if skipped:
            if settings.default_use_alternate_grabbing_method:
                splitter.grabBestAlternate(targeterrorstage2, settings.subdir1, settings.subdir3, outputFileName)
            else:
                splitter.grabBest(settings.default_top_n_stage3, settings.subdir1, settings.subdir3, outputFileName)
        else:
            if settings.default_use_alternate_grabbing_method:
                splitter.grabBestAlternate(targeterrorstage2, settings.subdir2, settings.subdir3, outputFileName)
            else:
                splitter.grabBest(settings.default_top_n_stage3, settings.subdir2, settings.subdir3, outputFileName)
        # sim them finally with all options enabled; html-output remains in subdir3, check cleanup for moving to results
        splitter.sim(settings.subdir3, "target_error=" + str(targeterror), player_profile, 2)
    else:
        printLog("No valid .result-files found for stage3!")


def stage1(player_profile):
    printLog("Entering Stage1")
    print("You have to choose one of the following modes for calculation:")
    print("1) Static mode uses a fixed amount, but less accurate calculations per profile (" + str(
        iterations_firstpart) + "," + str(iterations_secondpart) + "," + str(iterations_thirdpart) + ")")
    print("   It is however faster if simulating huge amounts of profiles")
    print(
        "2) Dynamic mode (preferred) lets you choose a specific 'correctness' of the calculation, but takes more time.")
    print(
        "   It uses the chosen target_error for the first part; in stage2 error lowers to " + str(
            target_error_secondpart) + " and " + str(
            target_error_thirdpart) + " for the final top " + str(settings.default_top_n_stage3))
    if settings.skip_questions:
        sim_mode = str(settings.auto_choose_static_or_dynamic)
    else:
        sim_mode = input("Please choose your mode (Enter to exit): ")
    if sim_mode == "1":
        static_stage1(player_profile)
    elif sim_mode == "2":
        dynamic_stage1(player_profile)
    else:
        print("Error, wrong mode: Stage1")
        printLog("Error, wrong mode: Stage1")
        sys.exit(0)


def stage2_restart():
    printLog("Restarting at Stage2")
    print("Restarting at Stage2")
    if not checkResultFiles(settings.subdir1):
        printLog("Error restarting at subdir: " + str(settings.subdir1))
        print("Error restarting at subdir: " + str(settings.subdir1))
    if settings.skip_questions:
        mode_choice = str(settings.auto_choose_static_or_dynamic)
    else:
        mode_choice = input("What mode did you use: Static (1) or dynamic (2): ")
    if mode_choice == "1":
        static_stage2()
    elif mode_choice == "2":
        if settings.skip_questions:
            new_te = settings.default_target_error_stage2
        else:
            new_te = input("Which target_error do you want to use for stage2: (Press enter for default: " + str(
                target_error_secondpart) + "):")
        if str(new_te) != str(target_error_secondpart) and splitter.user_targeterror != "0.0":
            dynamic_stage2(new_te, splitter.user_targeterror)
        else:
            dynamic_stage2(target_error_secondpart, splitter.user_targeterror)
    else:
        printLog("Error, wrong mode: Stage2_restart")
        print("Error, wrong mode: Stage2_restart")
        sys.exit(0)


def stage3_restart():
    printLog("Restarting at Stage3")
    print("Restarting at Stage3")
    if not checkResultFiles(settings.subdir2):
        printLog("Error restarting, some .result-files are empty in " + str(settings.subdir2))
        print("Error restarting at subdir: " + str(settings.subdir1))
    if settings.skip_questions:
        mode_choice = str(settings.auto_choose_static_or_dynamic)
    else:
        mode_choice = input("What mode did you use: Static (1) or dynamic (2): ")
    if mode_choice == "1":
        static_stage3()
    elif mode_choice == "2":
        if input("Did you skip stage 2? (y,n)") == "y":
            skip = True
        else:
            skip = False
        if settings.skip_questions:
            new_te = settings.default_target_error_stage3
        else:
            new_te = input("Which target_error do you want to use for stage3: (Press enter for default: " + str(
                target_error_thirdpart) + "):")
        if str(new_te) != str(target_error_thirdpart) and splitter.user_targeterror != "0.0":
            dynamic_stage3(skip, new_te, splitter.user_targeterror)
        else:
            dynamic_stage3(skip, target_error_thirdpart, splitter.user_targeterror)
    else:
        printLog("Error, wrong mode: Stage3_restart")
        print("Error, wrong mode: Stage3_restart")
        sys.exit(0)


def checkinterpreter():
    major, minor, _micro, _releaselevel, _serial = sys.version_info
    if major != 3:
        return False
    if minor < 6:
        return False
    return True


# just a workaround for skipping generation of out.simc
def getClassFromInput():
    config = configparser.ConfigParser()
    config.read(inputFileName, encoding='utf-8-sig')
    profile = config['Profile']
    return profile['class']


########################
#     Program Start    #
########################

def main():
    global b_quiet
    global s_stage
    global b_simcraft_enabled
    global class_spec

    error_handler = logging.FileHandler(errorFileName)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter("%(asctime)-15s %(levelname)s %(message)s"))

    # Handler to log messages to file
    log_handler = logging.FileHandler(logFileName)
    log_handler.setLevel(logging.INFO)
    log_handler.setFormatter(logging.Formatter("%(asctime)-15s %(levelname)s %(message)s"))

    # Handler for loging to stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(logging.Formatter("%(message)s"))

    logging.basicConfig(level=logging.DEBUG, handlers=[error_handler,
                                                       log_handler,
                                                       stdout_handler])

    # check version of python-interpreter running the script
    if not checkinterpreter():
        raise RuntimeError("Python-Version too old! You are running Python {}. Please install at least "
                           "Python-Version 3.6.x".format(sys.version))

    args = handleCommandLine()
    if args.quiet:
        stdout_handler.setLevel(logging.WARNING)
    if args.debug:
        log_handler.setLevel(logging.DEBUG)
        stdout_handler.setLevel(logging.DEBUG)
    validateSettings()

    # can always be rerun since it is now deterministic
    if s_stage == "stage1" or s_stage == "":
        start = datetime.datetime.now()
        player_profile = permutate()
        logging.info("Permutating took {}.".format(datetime.datetime.now()-start))
        outputGenerated = True
    else:
        if input(F"Do you want to generate {outputFileName} again? Press y to regenerate: ") == "y":
            player_profile = permutate()
            outputGenerated = True
        else:
            outputGenerated = False

    if not settings.skip_questions:
        if i_generatedProfiles > 50000:
            if input(
                    "-----> Beware: Computation with Simcraft might take a VERY long time with this amount of profiles!"
                    " <----- (Press Enter to continue, q to quit)") == "q":
                logging.info("Program exit by user")
                sys.exit(0)

    if outputGenerated:
        if i_generatedProfiles == 0:
            raise ValueError("No valid combinations found. Please check settings.py and your simpermut-export.")

    if b_simcraft_enabled:
        if outputGenerated:
            class_spec = player_profile.class_spec
        else:
            class_spec = getClassFromInput()

        if s_stage == "":
            s_stage = settings.default_sim_start_stage

        if s_stage == "stage1":
            stage1(player_profile)
        if s_stage == "stage2":
            if restart:
                if input("Do you want to restart stage 2?: (Enter to proceed, q to quit): ") == "q":
                    printLog("Restart aborted by user")
                else:
                    stage2_restart()
        if s_stage == "stage3":
            if input("Do you want to restart stage 3?: (Enter to proceed, q to quit): ") == "q":
                printLog("Restart aborted by user")
            else:
                stage3_restart()

    if settings.clean_up_after_step3:
        cleanup()


if __name__ == "__main__":
    try:
        main()
        logging.shutdown()
    except Exception as e:
        logging.error("Error: {}".format(e), exc_info=True)
        sys.exit(1)
