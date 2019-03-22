import math


class SimpleViterbiDecoder(object):
    """A simple Viterbi algorightm implementation.

    For Markov models with two hidden states and two emission letters. The
    states and the emissions are represented by 0 and 1.
    """

    def __init__(self, init_probs, transition_probs, emission_probs):
        """Initializer for the class.

        Args:
            init_probs: a vector of 2 floats, the initial probabilities
            for the hidden states
            transition_probs: a 2x2 matrix of floats, the transition
            probabilities, from current hidden state to next hidden states
            emission_probs: a 2x2 matrix of floats, the emission
            probabilities, from current hidden state to emissions
        """
        assert len(init_probs) == 2
        assert len(transition_probs) == 2
        assert list(map(len, transition_probs)) == [2, 2]
        assert len(emission_probs) == 2
        assert list(map(len, emission_probs)) == [2, 2]

        self._init_log = list(map(math.log, init_probs))
        self._transition_log = [list(map(math.log, xs)) for xs in transition_probs]
        self._emission_log = [list(map(math.log, xs)) for xs in emission_probs]

    def decode(self, emissions):
        """Run the Viterbi decoder.

        Args:
            emissions: a list of {0, 1} - the observed emissions

        Returns:
            a list of {0, 1} - the most likely sequence of hidden states
        """
        if not emissions:
            # Edge case, handle empty list here, to simplify the algorithm
            return []

        N = len(emissions)
        state_log = [[None, None] for i in range(N)]
        backtrack_info = [[None, None] for i in range(N)]

        # Forward pass, calculate the probabilities of states and the
        # back-tracking information.

        # The initial state probability estimates are treated separately
        # because these come from the initial distribution.
        state_log[0] = self._init_log
        state_log[0][0] += self._emission_log[0][emissions[0]]
        state_log[0][1] += self._emission_log[1][emissions[0]]

        # Successive state probability estimates are calculated using
        # the log-probabilities in the transition matrix.
        for i in range(1, N):
            for target in [0, 1]:
                from_0 = state_log[i - 1][0] + self._transition_log[0][target]
                from_1 = state_log[i - 1][1] + self._transition_log[1][target]
                emission_log = self._emission_log[target][emissions[i]]
                if from_0 > from_1:
                    backtrack_info[i][target] = 0
                    state_log[i][target] = from_0 + emission_log
                else:
                    backtrack_info[i][target] = 1
                    state_log[i][target] = from_1 + emission_log

        # Backward pass, find the most likely sequence of states.
        if state_log[N - 1][0] > state_log[N - 1][1]:
            state = 0
        else:
            state = 1

        states = [state]
        for i in range(N - 1, 0, -1):
            state = backtrack_info[i][state]
            states.append(state)
        states.reverse()

        return states
