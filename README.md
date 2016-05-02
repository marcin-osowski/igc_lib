A simple library to parse IGC logs and extract thermals.

Uses bearing rate-of-change cutoff, filtered using Viterbi algorithm.

The code is not pretty but has been battle-tested against
a couple hundred thousand IGC files. Detects various anomalies
in the logs and marks files as suspicious/invalid, providing
an explaination for the decision. Example usage:

```
  python igc_lib.py some_file.igc
```
