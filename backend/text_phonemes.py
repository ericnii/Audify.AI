from g2p_en import G2p

g2p = G2p()

def text_to_phonemes(text):
    phonemes = g2p(text)
    return list(phonemes)  # Returns ["HH", "EH", "L", "O"]