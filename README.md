A simple library to parse IGC logs and extract thermals.

Uses ground speed to detect flight and aircraft bearing rate of
change to detect thermalling. Both are smoothed using the
Viterbi algorithm.

The code has been battle-tested against a couple hundred thousand
IGC files. Detects various anomalies in the logs and marks files
as suspicious/invalid, providing an explaination for the decision.
If you find an IGC file on which the library misbehaves please
open a GitHub issue, we'd be happy to investigate.

Example usage:

```
  python igc_lib_demo.py some_file.igc
```

Should work both on Python 2.7 and on Python 3.
