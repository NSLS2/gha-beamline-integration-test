#!/usr/bin/env python3
import re
import yaml
from collections import defaultdict
from pathlib import Path
from typing import Any

from caproto import (ChannelChar, ChannelData, ChannelDouble, ChannelEnum,
                     ChannelInteger, ChannelString, ChannelNumeric)
from caproto.server import template_arg_parser, PVGroup, run

PLUGIN_TYPE_PVS = [
    (re.compile('image\\d:'), 'NDPluginStdArrays'),
    (re.compile('Stats\\d:'), 'NDPluginStats'),
    (re.compile('CC\\d:'), 'NDPluginColorConvert'),
    (re.compile('Proc\\d:'), 'NDPluginProcess'),
    (re.compile('Over\\d:'), 'NDPluginOverlay'),
    (re.compile('ROI\\d:'), 'NDPluginROI'),
    (re.compile('Trans\\d:'), 'NDPluginTransform'),
    (re.compile('netCDF\\d:'), 'NDFileNetCDF'),
    (re.compile('TIFF\\d:'), 'NDFileTIFF'),
    (re.compile('JPEG\\d:'), 'NDFileJPEG'),
    (re.compile('Nexus\\d:'), 'NDPluginNexus'),
    (re.compile('HDF\\d:'), 'NDFileHDF5'),
    (re.compile('Magick\\d:'), 'NDFileMagick'),
    (re.compile('TIFF\\d:'), 'NDFileTIFF'),
    (re.compile('HDF\\d:'), 'NDFileHDF5'),
    (re.compile('Current\\d:'), 'NDPluginStats'),
    (re.compile('SumAll'), 'NDPluginStats'),
]


class ReallyDefaultDict(defaultdict):
    def __contains__(self, key):
        return True

    def __missing__(self, key):
        if (key.endswith('-SP') or key.endswith('-I') or
                key.endswith('-RB') or key.endswith('-Cmd')):
            key, *_ = key.rpartition('-')
            return self[key]
        if key.endswith('_RBV') or key.endswith(':RBV'):
            return self[key[:-4]]
        ret = self[key] = self.default_factory(key)
        return ret

class BlackholeIOC(PVGroup):
    """
    IOC that spoofs a beamline.

    You can set up SubGroups for beamline components that interact with each other.
    """
    def __init__(self, *args, pv_specs_file: str | None = None, **kwargs):
        super().__init__(prefix="", *args, **kwargs)
        # Copy the original pvdb so we can use it for channels
        self.old_pvdb = self.pvdb.copy()
        # Reset the pvdb to use our fabricate_channel function
        self.pvdb = ReallyDefaultDict(self.fabricate_channel)
        # Load PV specifications from file
        self.pv_specs = self.load_pv_specs(pv_specs_file) if pv_specs_file else {}

    def load_pv_specs(self, pv_specs_file: str) -> dict[str, dict[str, Any]]:
        """Load PV specifications from YAML file."""
        specs_file = Path(pv_specs_file)
        if not specs_file.exists():
            print(f"Warning: PV specifications file not found: {specs_file}")
            return {}
        
        try:
            with open(specs_file) as f:
                data = yaml.safe_load(f)
                return data.get('pv_specs', {})
        except (yaml.YAMLError, IOError) as e:
            print(f"Warning: Could not load PV specifications: {e}")
            return {}

    def create_channel_from_spec(self, spec):
        """
        Create a channel object from a specification dictionary.
        
        Args:
            spec (dict): Dictionary containing channel specifications with keys:
                        - type: Channel type (e.g., 'ChannelDouble', 'ChannelInteger')
                        - value: Default value for the channel
                        - enum_strings: (optional) List of strings for ChannelEnum type
        
        Returns:
            Channel object of the specified type
        """
        channel_type = spec['type']
        value = spec['value']
        
        if channel_type == 'ChannelDouble':
            return ChannelDouble(value=value)
        elif channel_type == 'ChannelInteger':
            return ChannelInteger(value=value)
        elif channel_type == 'ChannelString':
            return ChannelString(value=value)
        elif channel_type == 'ChannelEnum':
            enum_strings = spec.get('enum_strings', [])
            return ChannelEnum(value=value, enum_strings=enum_strings)
        elif channel_type == 'ChannelChar':
            return ChannelChar(value=value)
        elif channel_type == "ChannelNumeric":
            return ChannelNumeric(value=value)
        elif channel_type == 'ChannelData':
            return ChannelData(value=value)
        else:
            raise ValueError(f"Unknown channel type: {channel_type}")

    def fabricate_channel(self, key):
        # Use existing channels if they exist
        if key in self.old_pvdb:
            return self.old_pvdb[key]
        
        # Check if we have a specification for this PV
        if key in self.pv_specs:
            return self.create_channel_from_spec(self.pv_specs[key])
        
        # Fall back to default channel type detection
        if 'PluginType' in key:
            for pattern, val in PLUGIN_TYPE_PVS:
                if pattern.search(key):
                    return ChannelString(value=val)
        elif 'ArrayPort' in key:
            return ChannelString(value=key)
        elif 'PortName' in key:
            return ChannelString(value=key)
        elif 'EnableCallbacks' in key:
            return ChannelEnum(value=0, enum_strings=['Disabled', 'Enabled'])
        elif 'BlockingCallbacks' in key:
            return ChannelEnum(value=0, enum_strings=['No', 'Yes'])
        elif 'Auto' in key:
            return ChannelEnum(value=0, enum_strings=['No', 'Yes'])
        elif 'ImageMode' in key:
            return ChannelEnum(value=0, enum_strings=['Single', 'Multiple', 'Continuous'])
        elif 'WriteMode' in key:
            return ChannelEnum(value=0, enum_strings=['Single', 'Capture', 'Stream'])
        elif 'ArraySize' in key:
            return ChannelData(value=10)
        elif 'TriggerMode' in key:
            return ChannelEnum(value=0, enum_strings=[
                'Internal', 'External', 'Free Run', 'Sync In 1', 'Sync In 2', 'Sync In 3', 'Sync In 4', 'Fixed Rate', 'Software'])
        elif 'FileWriteMode' in key:
            return ChannelEnum(value=0, enum_strings=['Single'])
        elif 'FilePathExists' in key:
            return ChannelData(value=1)
        elif 'WaitForPlugins' in key:
            return ChannelEnum(value=0, enum_strings=['No', 'Yes'])
        elif ('file' in key.lower() and 'number' not in key.lower() and
            'mode' not in key.lower()):
            return ChannelChar(value='a' * 250)
        elif ('filenumber' in key.lower()):
            return ChannelInteger(value=0)
        elif 'Compression' in key:
            return ChannelEnum(value=0, enum_strings=['None', 'N-bit', 'szip', 'zlib', 'blosc'])
        elif key.endswith(".EGU"):
            return ChannelString(value="mm")
        return ChannelDouble(value=0.0)


def main():
    parser, split_args = template_arg_parser(
        default_prefix='',
        desc="Spoof a beamline IOC with configurable PVs")
    parser.add_argument('--pv-specs', type=str, default=None,
                      help='Path to YAML file containing PV specifications')
    parser.add_argument('--no-warning', action='store_true',
                      help='Skip the warning message')
    args = parser.parse_args()
    _, run_options = split_args(args)
    run_options['interfaces'] = ['127.0.0.1']

    if not args.no_warning:
        print('''
*** WARNING ***
This script spawns an EPICS IOC which responds to ALL caget, caput, camonitor
requests.  As this is effectively a PV black hole, it may affect the
performance and functionality of other IOCs on your network.

The script ignores the --interfaces command line argument, always
binding only to 127.0.0.1, superseding the usual default (0.0.0.0) and any
user-provided value.
*** WARNING ***

Press return if you have acknowledged the above, or Ctrl-C to quit.''')

        try:
            input()
        except KeyboardInterrupt:
            print()
            return

    print('''

                         PV blackhole started

''')
    
    # Create IOC with specified PV specs file
    ioc = BlackholeIOC(pv_specs_file=args.pv_specs)
    run(ioc.pvdb, **run_options)


if __name__ == '__main__':
    main()
