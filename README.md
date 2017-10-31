# Telemetric

[![Build Status](https://travis-ci.org/knipknap/telemetric.svg?branch=master)](https://travis-ci.org/knipknap/telemetric)
[![Coverage Status](https://coveralls.io/repos/github/knipknap/telemetric/badge.svg?branch=master)](https://coveralls.io/github/knipknap/telemetric?branch=master)
[![Code Climate](https://lima.codeclimate.com/github/knipknap/telemetric/badges/gpa.svg)](https://lima.codeclimate.com/github/knipknap/telemetric)
[![Documentation Status](https://readthedocs.org/projects/telemetric/badge/?version=latest)](http://telemetric.readthedocs.io/en/latest/?badge=latest)

## Summary

Telemetric is a [Telemetry](https://www.ietf.org/archive/id/draft-wu-t2trg-network-telemetry-00.txt) client.
Telemetric is work in progress.

## Do you need commercial support?

Telemetric is supported by [Procedure 8](https://procedure8.com). Get in touch if you need anything!

### Example

The following example prints all received messages to stdout.

```python
from telemetric import TMClient

client = TMClient('192.168.0.1', 8777, print_all=True)
client.run()
```

## Documentation

For full documentation please refer to

  http://telemetric.readthedocs.io
