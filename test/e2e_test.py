#
#	gpg-mailgate
#
#	This file is part of the gpg-mailgate source code.
#
#	gpg-mailgate is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	gpg-mailgate source code is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with gpg-mailgate source code. If not, see <http://www.gnu.org/licenses/>.
#

import os
import sys

import subprocess

import difflib

import configparser
import logging

from time import sleep

RELAY_SCRIPT = "test/relay.py"
CONFIG_FILE = "test/gpg-mailgate.conf"

def build_config(config):
    cp = configparser.ConfigParser()

    cp.add_section("logging")
    cp.set("logging", "file", config["log_file"])
    cp.set("logging", "verbose", "yes")

    cp.add_section("gpg")
    cp.set("gpg", "keyhome", config["gpg_keyhome"])

    cp.add_section("smime")
    cp.set("smime", "cert_path", config["smime_certpath"])

    cp.add_section("relay")
    cp.set("relay", "host", "localhost")
    cp.set("relay", "port", config["port"])

    cp.add_section("enc_keymap")
    cp.set("enc_keymap", "alice@disposlab", "1CD245308F0963D038E88357973CF4D9387C44D7")
    cp.set("enc_keymap", "bob@disposlab", "19CF4B47ECC9C47AFA84D4BD96F39FDA0E31BB67")

    logging.debug(f"Created config with keyhome={config['gpg_keyhome']}, cert_path={config['smime_certpath']} and relay at port {config['port']}")
    return cp

def write_test_config(outfile, **config):
    logging.debug(f"Generating configuration with {config!r}")

    out = open(outfile, "w+")
    cp = build_config(config)
    cp.write(out)
    out.close()

    logging.debug(f"Wrote configuration to {outfile}")

def load_file(name):
	f = open(name, 'r')
	contents = f.read()
	f.close()

	return bytes(contents, 'utf-8')

def report_result(message_file, expected, test_output):
    status = None
    if expected in test_output:
        status = "Success"
    else:
        status = "Failure"

    print(message_file.ljust(30), status)

def execute_e2e_test(case_name, config, config_path):
    """Read test case configuration from config and run that test case.

    Parameter case_name should refer to a section in test
    config file.  Each of these sections should contain
    following properties: 'descr', 'to', 'in' and 'out'.
    """
    # This environment variable is set in Makefile.
    python_path = os.getenv('PYTHON', 'python3')

    gpglacre_cmd = [python_path,
                    "gpg-mailgate.py",
                    config.get(case_name, "to")]

    relay_cmd = [python_path,
                 config.get("relay", "script"),
                 config.get("relay", "port")]

    logging.debug(f"Spawning relay: {relay_cmd}")
    relay_proc = subprocess.Popen(relay_cmd,
                                  stdin = None,
                                  stdout = subprocess.PIPE)

    logging.debug(f"Spawning GPG-Lacre: {gpglacre_cmd}, stdin = {config.get(case_name, 'in')}")

    # pass PATH because otherwise it would be dropped
    gpglacre_proc = subprocess.run(gpglacre_cmd,
                                   input = load_file(config.get(case_name, "in")),
                                   capture_output = True,
                                   env = {"GPG_MAILGATE_CONFIG": config_path,
                                          "PATH": os.getenv("PATH")})

    # Let the relay process the data.
    relay_proc.wait()

    (testout, _) = relay_proc.communicate()
    testout = testout.decode('utf-8')

    logging.debug(f"Read {len(testout)} characters of test output: '{testout}'")

    report_result(config.get(case_name, "in"), config.get(case_name, "out"), testout)

def load_test_config():
    cp = configparser.ConfigParser()
    cp.read("test/e2e.ini")

    return cp


config = load_test_config()

logging.basicConfig(filename	= config.get("tests", "e2e_log"),
                    # Get raw values of log and date formats because they
                    # contain %-sequences and we don't want them to be expanded
                    # by the ConfigParser.
                    format		= config.get("tests", "e2e_log_format", raw=True),
                    datefmt		= config.get("tests", "e2e_log_datefmt", raw=True),
                    level		= logging.DEBUG)

config_path = os.getcwd() + "/" + CONFIG_FILE

write_test_config(config_path,
                  port				= config.get("relay", "port"),
                  gpg_keyhome		= config.get("dirs", "keys"),
                  smime_certpath	= config.get("dirs", "certs"),
                  log_file			= config.get("tests", "lacre_log"))

for case_no in range(1, config.getint("tests", "cases")+1):
    case_name = f"case-{case_no}"
    logging.info(f"Executing {case_name}: {config.get(case_name, 'descr')}")

    execute_e2e_test(case_name, config, config_path)

print("See diagnostic output for details. Tests: '%s', Lacre: '%s'" % (config.get("tests", "e2e_log"), config.get("tests", "lacre_log")))
