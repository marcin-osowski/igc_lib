#!/usr/bin/env python
"""A tool to learn Viterbi filter (Markov model) parameters from IGC files.

Learns parameters for the circling/not circling filter. Training data is
loaded from a directory.
"""

import os
import sys
from Bio.Alphabet import Alphabet
from Bio.HMM.MarkovModel import MarkovModelBuilder
from Bio.HMM.Trainer import BaumWelchTrainer
from Bio.HMM.Trainer import TrainingSequence
from Bio.Seq import Seq

import igc_lib


def list_igc_files(directory):
    files = []
    for entry in os.listdir(directory):
        full_entry = os.path.join(directory, entry)
        if os.path.isfile(full_entry) and entry.endswith('.igc'):
            files.append(full_entry)
    return files


def initial_markov_model():
    state_alphabet = Alphabet()
    state_alphabet.letters = list("cs")
    emissions_alphabet = Alphabet()
    emissions_alphabet.letters = list("CS")

    mmb = MarkovModelBuilder(state_alphabet, emissions_alphabet)
    mmb.set_initial_probabilities({'c': 0.05, 's': 0.95})
    mmb.allow_all_transitions()
    mmb.set_transition_score('c', 'c', 0.95)
    mmb.set_transition_score('c', 's', 0.05)
    mmb.set_transition_score('s', 'c', 0.05)
    mmb.set_transition_score('s', 's', 0.95)
    mmb.set_emission_score('c', 'C', 0.80)
    mmb.set_emission_score('c', 'S', 0.20)
    mmb.set_emission_score('s', 'C', 0.20)
    mmb.set_emission_score('s', 'S', 0.80)
    mm = mmb.get_markov_model()
    return mm


def get_flight_training_sequence(flight):
    state_alphabet = Alphabet()
    state_alphabet.letters = list("cs")
    emissions_alphabet = Alphabet()
    emissions_alphabet.letters = list("CS")

    emissions = []
    for x in flight._circling_emissions():
        if x == 1:
            emissions.append("C")
        else:
            emissions.append("S")
    emissions = Seq("".join(emissions), emissions_alphabet)
    empty_states = Seq("", state_alphabet)
    return TrainingSequence(emissions, empty_states)


def get_training_sequences(files):
    sequences = []
    for fname in files:
        flight = igc_lib.Flight.create_from_file(fname)
        if flight.valid:
            sequences.append(get_flight_training_sequence(flight))
    return sequences


def stop_function(log_likelihood_change, num_iterations):
    print "log_likehood_change: %f" % log_likelihood_change
    print "num_iterations: %d" % num_iterations
    if num_iterations >= 20:
        return 1
    else:
        return 0


def main():
    if len(sys.argv) != 2:
        print "Usage: %s directory_with_igc_files"
        sys.exit(1)

    learning_dir = sys.argv[1]
    files = list_igc_files(learning_dir)
    print "Found %d IGC files in '%s'." % (len(files), learning_dir)

    print "Reading and processing files"
    training_sequences = get_training_sequences(files)
    print "Found %d valid tracks." % len(training_sequences)

    if len(training_sequences) == 0:
        print "Found no valid tracks. Aborting."
        sys.exit(1)

    mm = initial_markov_model()
    trainer = BaumWelchTrainer(mm)
    trainer.train(training_sequences, stop_function)

    print "Training complete!"
    print "mm.emission_prob:", mm.emission_prob
    print "mm.transition_prob:", mm.transition_prob


if __name__ == "__main__":
    main()
