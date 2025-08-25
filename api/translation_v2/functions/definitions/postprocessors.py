import re


def fix_repeated_subsentence(sentence: str) -> str:
    words = sentence.split()
    n = len(words)

    for size in range(n // 2, 0, -1):
        for i in range(n - size * 3 + 1):
            subsentence = ' '.join(words[i:i + size])
            pattern = rf'({re.escape(subsentence)})(?:\s+\1){{2,}}'

            if re.search(pattern, sentence):
                sentence = re.sub(pattern, r'\1 ', sentence)
                sentence = re.sub(r'\s{2,}', ' ', sentence)
                words = sentence.split()
                n = len(words)
                break

    return sentence.strip()
