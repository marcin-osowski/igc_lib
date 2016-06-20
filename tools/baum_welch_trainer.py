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

# A hack to import from the parent directory
sys.path.insert(0, '..')
import igc_lib


def list_igc_files(directory):
    files = []
    for entry in os.listdir(directory):
        full_entry = os.path.join(directory, entry)
        if os.path.isfile(full_entry) and entry.endswith('.igc'):
            files.append(full_entry)
    return files


def initial_markov_model_circling():
    state_alphabet = Alphabet()
    state_alphabet.letters = list("cs")
    emissions_alphabet = Alphabet()
    emissions_alphabet.letters = list("CS")

    mmb = MarkovModelBuilder(state_alphabet, emissions_alphabet)
    mmb.set_initial_probabilities({'c': 0.20, 's': 0.80})
    mmb.allow_all_transitions()
    mmb.set_transition_score('c', 'c', 0.90)
    mmb.set_transition_score('c', 's', 0.10)
    mmb.set_transition_score('s', 'c', 0.10)
    mmb.set_transition_score('s', 's', 0.90)
    mmb.set_emission_score('c', 'C', 0.90)
    mmb.set_emission_score('c', 'S', 0.10)
    mmb.set_emission_score('s', 'C', 0.10)
    mmb.set_emission_score('s', 'S', 0.90)
    mm = mmb.get_markov_model()
    return mm


def initial_markov_model_flying():
    state_alphabet = Alphabet()
    state_alphabet.letters = list("fs")
    emissions_alphabet = Alphabet()
    emissions_alphabet.letters = list("FS")

    mmb = MarkovModelBuilder(state_alphabet, emissions_alphabet)
    mmb.set_initial_probabilities({'f': 0.20, 's': 0.80})
    mmb.allow_all_transitions()
    mmb.set_transition_score('f', 'f', 0.99)
    mmb.set_transition_score('f', 's', 0.01)
    mmb.set_transition_score('s', 'f', 0.01)
    mmb.set_transition_score('s', 's', 0.99)
    mmb.set_emission_score('f', 'F', 0.90)
    mmb.set_emission_score('f', 'S', 0.10)
    mmb.set_emission_score('s', 'F', 0.10)
    mmb.set_emission_score('s', 'S', 0.90)
    mm = mmb.get_markov_model()
    return mm


def get_circling_sequence(flight):
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


def get_flying_sequence(flight):
    state_alphabet = Alphabet()
    state_alphabet.letters = list("fs")
    emissions_alphabet = Alphabet()
    emissions_alphabet.letters = list("FS")

    emissions = []
    for x in flight._flying_emissions():
        if x == 1:
            emissions.append("F")
        else:
            emissions.append("S")
    emissions = Seq("".join(emissions), emissions_alphabet)
    empty_states = Seq("", state_alphabet)
    return TrainingSequence(emissions, empty_states)


def get_training_sequences(files):
    circling_sequences = []
    flying_sequences = []
    for fname in files:
        flight = igc_lib.Flight.create_from_file(fname)
        if flight.valid:
            circling_sequences.append(get_circling_sequence(flight))
            flying_sequences.append(get_flying_sequence(flight))
    return circling_sequences, flying_sequences


def stop_function(log_likelihood_change, num_iterations):
    print "num_iterations: %d" % num_iterations,
    print "log_likelihood_change: %f" % log_likelihood_change
    return log_likelihood_change < 0.05 and num_iterations > 5


def main():
    if len(sys.argv) != 2:
        print "Usage: %s directory_with_igc_files"
        sys.exit(1)

    learning_dir = sys.argv[1]
    files = list_igc_files(learning_dir)
    print "Found %d IGC files in '%s'." % (len(files), learning_dir)

    print "Reading and processing files"
    circling_sequences, flying_sequences = get_training_sequences(files)
    print "Found %d valid tracks." % len(circling_sequences)

    if len(circling_sequences) == 0:
        print "Found no valid tracks. Aborting."
        sys.exit(1)

    flying_mm = initial_markov_model_flying()
    trainer = BaumWelchTrainer(flying_mm)
    trainer.train(flying_sequences, stop_function)
    print "Flying model training complete!"

    circling_mm = initial_markov_model_circling()
    trainer = BaumWelchTrainer(circling_mm)
    trainer.train(circling_sequences, stop_function)
    print "Circling model training complete!"

    print "flying_mm.transition_prob:", flying_mm.transition_prob
    print "flying_mm.emission_prob:", flying_mm.emission_prob
    print "circling_mm.transition_prob:", circling_mm.transition_prob
    print "circling_mm.emission_prob:", circling_mm.emission_prob


if __name__ == "__main__":
    main()
