#!/usr/bin/env python3
"""
Temporarily apply `ufw` rules

This script allows you to add rules to `ufw` (Uncomplicated Firewall) with a
time to live. You can then run the script as a cronjob (with the --clean flag)
to clean up (remove) the expired rules.

Arguments:
        -h, --help                       show the help message and exit
        -s, --status                     show rule list with expirations
        -c, --clean                      clean up expired rules
        -r RULE, --rule RULE             rule to be added to `ufw`
        -p POSITION, --position POSITION position to add the rule
        -t TTL, --ttl TTL                time to live for the rule
"""
__author__  = 'Joshua Sherman and Emrecan ÖKSÜM'
__file__    = 'tmpufw'
__license__ = 'MIT'
__status__  = 'Production'
__version__ = '1.0.1'

"""
TMPUFW by Joshua Sherman
Small fixes and improvements to it by Emrecan ÖKSÜM
"""

from argparse import ArgumentParser
from datetime import datetime
import os
from os import getpid, makedirs, path, remove, unlink, popen
from parsedatetime import Calendar
from shutil import move
from subprocess import CalledProcessError, check_output, STDOUT
from sys import exit
from time import mktime, time

class tmpufw(object):
        parser = ArgumentParser(description = 'Temporarily apply `ufw` rules')

        def __init__(self):
                self.parser.add_argument('-s', '--status', action = 'store_true', help = 'show rule list with expirations')
                self.parser.add_argument('-c', '--clean', action = 'store_true', help = 'clean up expired rules')
                self.parser.add_argument('-r', '--rule', help = 'rule to be added to `ufw`')
                self.parser.add_argument('-p', '--position', default = 1, help = 'position to add the rule')
                self.parser.add_argument('-t', '--ttl', default = '30 days', help = 'time to live for the rule')
                args = self.parser.parse_args()

                # Our file names
                pid_file       = '/var/run/' + __file__ + '.pid'
                rules_file     = '/usr/local/share/' + __file__ + '/rules'
                tmp_rules_file = '/tmp/' + __file__ + '-rules'

                if args.status:
                        if path.exists(rules_file):
                                try:
                                        print("Expiration\t\tRule")
                                        print('=' * 80)

                                        # Loops through the rules lines
                                        for line in open(rules_file, 'r'):
                                                # Breaks apart line into expiration timestamp and rule
                                                timestamp, rule = line.strip("\n").split(' ', 1)

                                                print(str(datetime.fromtimestamp(float(timestamp))) + "\t" + rule)
                                except IOError:
                                        self.error('unable to read from the rules file: ' + rules_file)
                        else:
                                self.error('there are no rules to display')
                elif args.clean:
                        # Checks for PID file
                        if path.exists(pid_file):
                                pfo = open(pid_file, "r")
                                opid = pfo.read()
                                pfo.close()

                                opid = opid.strip()
                                pcmd = os.popen("ps aux | grep " + opid + " | grep " + __file__ + " | grep -v grep")
                                cmdr = pcmd.read()

                                if cmdr.find(__file__) == -1:
                                        print(__file__ + " pidfile is found but process doesn't seem to be running! Unlinking the PID...")
                                        os.unlink(pid_file)
                                        self.error(__file__ + " will run in the next crond invokation.")
                                self.error(__file__ + ' is already running')
                        else:
                                # Creates the PID file
                                try:
                                        handle = open(pid_file, 'w')
                                        handle.write(str(getpid()))
                                        handle.close()
                                except IOError:
                                        self.error('unable to create PID file: ' + pid_file)

                                # Checks for the rules file
                                if path.exists(rules_file):
                                        # Opens the temporary rules file
                                        try:
                                                handle = open(tmp_rules_file, 'a')
                                        except IOError:
                                                self.error('unable to write to the tmp rules file: ' + tmp_rules_file)

                                        try:
                                                current_time = time()

                                                # Loops through the rules lines
                                                for line in open(rules_file, 'r'):
                                                        # Breaks apart line into expiration timestamp and rule
                                                        timestamp, rule = line.strip("\n").split(' ', 1)

                                                        # Checks if rule has expired
                                                        if current_time < float(timestamp):
                                                                handle.write(line)
                                                                print(str(datetime.fromtimestamp(time())) + "\tskipped rule\t" + rule)
                                                        else:
                                                                try:
                                                                        self.ufw_execute('delete ' + rule)
                                                                        print(str(datetime.fromtimestamp(time())) + "\tdeleted rule\t" + rule)
                                                                except CalledProcessError as error:
                                                                        self.ufw_error(error)

                                                handle.close()

                                                # Moves the tmp file to the rules file
                                                move(tmp_rules_file, rules_file)
                                        except IOError:
                                                self.error('unable to from the read rules file: ' + rules_file)

                                # Removes the PID
                                remove(pid_file)
                elif args.rule:
                        rules_path = path.dirname(rules_file)

                        if not path.exists(rules_path):
                                makedirs(rules_path)

                        # Converts the TTL to a timestamp
                        cal       = Calendar()
                        timestamp = mktime(cal.parse(args.ttl)[0])

                        # Writes the rule to the rules file
                        try:
                                handle = open(rules_file, "r")
                                ruleLines = handle.readlines()
                                handle.close()
                                updatedExistingRule = 0
                                nruleLines = ruleLines.copy()
                                for id, rule in enumerate(ruleLines):
                                        if rule.find(args.rule) != -1:
                                                updatedExistingRule = 1
                                                print("Rule found! updating existing rule...")
                                                erule = rule.split(" ")
                                                erule[0] = str(timestamp)
                                                erule = " ".join(erule)
                                                nruleLines[id] = erule

                                if updatedExistingRule == 0:
                                        handle = open(rules_file, 'a')
                                        handle.write(str(timestamp) + ' ' + args.rule)
                                        handle.write("\n")
                                        handle.close()
                                else:
                                        handle = open(rules_file, 'w')
                                        handle.writelines(nruleLines)
                                        handle.close()
                        except IOError:
                                self.error('unable to write to the rules file: ' + rules_file)

                        # Attempts to add the rule to `ufw`
                        try:
                                self.ufw_execute('insert ' + str(args.position) + ' ' + args.rule)
                        except CalledProcessError as error:
                                # Catches an error when attempting to add a rule to an empty database
                                if error.output == b"ERROR: Invalid position '1'\n":
                                        try:
                                                self.ufw_execute(args.rule)
                                        except CalledProcessError as error:
                                                self.ufw_error(error)
                                else:
                                        self.ufw_error(error)
                else:
                        self.error('no arguments specified')

        def error(self, message):
                self.parser.print_usage()
                print(__file__ + ': error: ' + message)
                exit(2)

        def ufw_execute(self, rule):
                for arg in [' --dry-run ', ' ']:
                        command = 'ufw' + arg + rule
                        check_output(command, stderr = STDOUT, shell = True)

        def ufw_error(self, error):
                self.error('ufw: ' + error.output.decode(encoding = 'UTF-8'))

if __name__ == '__main__':
        tmpufw()
