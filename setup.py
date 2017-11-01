import sys
import os
from setuptools import setup, find_packages
sys.path.insert(0, 'telemetric')
from version import __version__

descr = '''
Telemetric is an implementation of the IETF Telemetry network protocol.
'''.strip()

# Run the setup.
setup(name='telemetric',
      version=__version__,
      description='An implementation of the IETF Telemetry network protocol',
      long_description=descr,
      author='Samuel Abels',
      author_email='knipknap@gmail.com',
      license='MIT',
      package_dir={'telemetric': 'telemetric'},
      packages=find_packages(),
      include_package_data=True,
      scripts=['scripts/telemetric'],
      install_requires = ['protobuf',
                          'Exscript>=2.4'],
      test_suite='tests',
      keywords=' '.join(['telemetric',
                         'telemetry',
                         'network',
                         'networking',
                         'client']),
      url='https://github.com/knipknap/telemetric',
      classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing :: Markup :: XML'
      ])
