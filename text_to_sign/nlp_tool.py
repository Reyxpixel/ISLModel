# # # import spacy
# # # import sys

# # # # Load SpaCy model
# # # nlp = spacy.load("en_core_web_sm")

# # # WH_WORDS = {"who", "what", "where", "when", "why", "how", "which"}
# # # TIME_WORDS = {"yesterday", "today", "tomorrow", "tonight", "now", "always"}
# # # # 'Be' verbs should be dropped in ISL gloss
# # # BE_VERBS = {"be", "is", "am", "are", "was", "were", "been", "being"}

# # # def get_noun_phrase(token):
# # #     """
# # #     Extracts the noun along with its compounds and adjectives.
# # #     Follows ISL Rule: [Compound] + [Noun] + [Adjective]
# # #     Example: 'The big meeting room' -> 'MEETING ROOM BIG'
# # #     """
# # #     compounds = [child.text.upper() for child in token.children if child.dep_ == "compound"]
# # #     adjectives = [child.text.upper() for child in token.children if child.dep_ in ["amod", "acomp"]]

# # #     # Use lemma for standard nouns (rooms -> ROOM), but exact text for pronouns (I, IT)
# # #     base_word = token.text.upper() if token.pos_ in ["PRON", "PROPN"] else token.lemma_.upper()

# # #     phrase = []
# # #     if compounds:
# # #         phrase.extend(compounds)
# # #     phrase.append(base_word)
# # #     if adjectives:
# # #         phrase.extend(adjectives)

# # #     return " ".join(phrase)
# # # def convert_to_isl(sentence):
# # #     doc = nlp(sentence.lower())

# # #     subject = None
# # #     objects = []
# # #     main_verb = None
# # #     secondary_verbs = []
# # #     negation = False
# # #     adverbs = []
# # #     time_expressions = []
# # #     wh_word = None
# # #     is_continuous = False
# # #     interjections = [] # NEW: Capture things like "Hello", "Yes", "No"

# # #     for token in doc:
# # #         # 1. Interjections (Hello, Hi, Wow)
# # #         if token.pos_ == "INTJ":
# # #             interjections.append(token.lemma_.upper())
# # #             continue

# # #         # 2. Wh-Words
# # #         if token.text in WH_WORDS:
# # #             wh_word = token.text.upper()
# # #             continue

# # #         # 3. Time Words
# # #         if token.text in TIME_WORDS:
# # #             time_expressions.append(token.text.upper())
# # #             continue

# # #         # 4. Subjects
# # #         if token.dep_ in ["nsubj", "nsubjpass"]:
# # #             subject = get_noun_phrase(token)

# # #         # 5. Objects and Complements
# # #         if token.dep_ in ["dobj", "obj", "pobj", "attr", "acomp"]:
# # #             objects.append(get_noun_phrase(token))

# # #         # 6. Verbs
# # #         if token.pos_ in ["VERB", "AUX"]:
# # #             if token.lemma_ in BE_VERBS:
# # #                 continue
# # #             if token.tag_ == "VBG":
# # #                 is_continuous = True

# # #             if token.dep_ == "ROOT":
# # #                 main_verb = token.lemma_.upper()
# # #             elif token.dep_ != "ROOT" and token.lemma_.upper() != main_verb:
# # #                 secondary_verbs.append(token.lemma_.upper())

# # #         # 7. Negation
# # #         if token.dep_ == "neg":
# # #             negation = True

# # #         # 8. Adverbs
# # #         if token.pos_ == "ADV" and token.text not in TIME_WORDS and token.text not in WH_WORDS:
# # #             adverbs.append(token.text.upper())

# # #     # --- ASSEMBLE THE ISL GLOSS ---
# # #     isl_tokens = []

# # #     # Interjections usually start the sentence
# # #     isl_tokens.extend(interjections)
# # #     isl_tokens.extend(time_expressions)

# # #     if subject:
# # #         isl_tokens.append(subject)

# # #     isl_tokens.extend(objects)
# # #     isl_tokens.extend(secondary_verbs)

# # #     if main_verb:
# # #         isl_tokens.append(main_verb)

# # #     if is_continuous and main_verb:
# # #         isl_tokens.append("CONTINUE")

# # #     if negation:
# # #         isl_tokens.append("NOT")

# # #     isl_tokens.extend(adverbs)

# # #     if wh_word:
# # #         isl_tokens.append(wh_word)

# # #     final_gloss = " ".join(isl_tokens).strip()

# # #     # --- NEW: THE FRAGMENT FALLBACK ---
# # #     # If the sentence had no verbs or objects (like "Hello World"),
# # #     # just extract the core concepts in order so it doesn't return blank.
# # #     if not final_gloss:
# # #         fallback = [token.lemma_.upper() for token in doc if token.pos_ in ["INTJ", "NOUN", "PROPN", "ADJ"]]
# # #         return " ".join(fallback)

# # #     return final_gloss

# # # if __name__ == "__main__":
# # #     # If a sentence is passed as a command line argument, process it and print
# # #     if len(sys.argv) > 1:
# # #         sentence = sys.argv[1]
# # #         print(convert_to_isl(sentence))
# # #     else:
# # #         print("Error: No input provided.")


# # import spacy
# # import sys
# # import re

# # def protect_placeholders(sentence):
# #     placeholders = {}

# #     def repl(match):
# #         key = f"PLACEHOLDER{len(placeholders)}"
# #         placeholders[key] = match.group(0)   # Stores "[KUNAL]"
# #         return key

# #     protected = re.sub(r"\[[^\]]+\]", repl, sentence)
# #     return protected, placeholders

# # # Load SpaCy model
# # nlp = spacy.load("en_core_web_sm")

# # WH_WORDS = {"who", "what", "where", "when", "why", "how", "which"}
# # TIME_WORDS = {"yesterday", "today", "tomorrow", "tonight", "now", "always"}
# # BE_VERBS = {"be", "is", "am", "are", "was", "were", "been", "being"}

# # def get_noun_phrase(token):
# #     compounds = [child.text.upper() for child in token.children if child.dep_ == "compound"]
# #     adjectives = [child.text.upper() for child in token.children if child.dep_ in ["amod", "acomp"]]
# #     numbers = [child.text.upper() for child in token.children if child.dep_ == "nummod"]
# #     #base_word = token.text.upper() if token.pos_ in ["PRON", "PROPN"] else token.lemma_.upper()
# #     if token.text.upper().startswith("PLACEHOLDER"):
# #         base_word = token.text.upper()
# #     elif token.pos_ in ["PRON", "PROPN"]:
# #         base_word = token.text.upper()
# #     else:
# #         base_word = token.lemma_.upper()
    
# #     phrase = []
# #     if compounds:
# #         phrase.extend(compounds)
# #     phrase.append(base_word)
# #     if adjectives:
# #         phrase.extend(adjectives)
# #     if numbers:
# #         phrase.extend(numbers)
        
# #     return " ".join(phrase)

# # def convert_to_isl(sentence):
# #     sentence, placeholders = protect_placeholders(sentence)
# #     doc = nlp(sentence)
# #     # for token in doc:
# #     #     print(
# #     #         token.text,
# #     #         token.pos_,
# #     #         token.dep_,
# #     #         token.head.text
# #     #     )
# #     interjections = []
# #     time_expressions = []
# #     wh_word = None
# #     # Clause buckets for handling multiple verbs sequentially: [Subject -> Object -> Verb]
# #     clauses = {}

# #     for token in doc:
# #         if token.pos_ in ["VERB", "AUX"] or token.dep_ == "ROOT":
# #             is_be_verb = token.lemma_ in BE_VERBS
# #             if is_be_verb and token.dep_ != "ROOT":
# #                 continue
# #             clauses[token] = {
# #                 "subject": None,
# #                 "objects": [],
# #                 "secondary_verbs": [],
# #                 "adverbs": [],
# #                 "main_verb": (
# #                     token.lemma_.upper()
# #                     if token.pos_ in ["VERB", "AUX"] and not is_be_verb
# #                     else ""
# #                 ),                    
# #                 # "main_verb": "" if is_be_verb else token.lemma_.upper(),
# #                 "negation": False,
# #                 "is_continuous": (token.tag_ == "VBG")
# #             }
            
# #         #    clauses[token] = {
# #         #        "subject": None,
# #         #        "objects": [],
# #         #        "secondary_verbs": [],
# #         #        "main_verb": "" if is_be_verb else token.lemma_.upper(),
# #         #        "negation": False,
# #         #        "is_continuous": (token.tag_ == "VBG")
# #         #    } 
        
# #     for token in doc:
# #         if token.pos_ == "INTJ":
# #             interjections.append(token.lemma_.upper())
# #             continue
# #         if token.text.lower() in WH_WORDS:
# #             wh_word = token.text.upper()
# #             continue
# #         if token.text.lower() in TIME_WORDS:
# #             time_expressions.append(token.text.upper())
# #             continue
        
# #         # if token.pos_ == "ADV" and token.text not in TIME_WORDS and token.text not in WH_WORDS:
# #         #     adverbs.append(token.text.upper())
# #         #     continue
# #         # if token.pos_ == "ADV" and token.text not in TIME_WORDS and token.text not in WH_WORDS:
# #         #     parent = token
# #         #     while parent not in clauses:
# #         #         if parent == parent.head:
# #         #             break
# #         #         parent = parent.head
# #         #     if parent in clauses:
# #         #         clauses[parent]["adverbs"].append(token.text.upper())
# #         #     continue
        
# #         if token in clauses:
# #             continue
# #         parent = token 
# #         while parent not in clauses:
# #             if parent == parent.head:
# #                 break
# #             parent = parent.head

# #         # if parent in clauses:
# #         #     if token.dep_ in ["nsubj", "nsubjpass"]:
# #         #         clauses[parent]["subject"] = get_noun_phrase(token)
# #         #     elif token.dep_ in ["dobj", "obj", "pobj", "attr", "acomp"]:
# #         #         clauses[parent]["objects"].append(get_noun_phrase(token))
# #         #     elif token.pos_ == "AUX" and token.lemma_ not in BE_VERBS:
# #         #         clauses[parent]["secondary_verbs"].append(token.lemma_.upper())
# #         #     elif token.dep_ == "neg":
# #         #         clauses[parent]["negation"] = True
# #         if parent in clauses:
# #             if token.dep_ in ["nsubj", "nsubjpass"]:
# #                 clauses[parent]["subject"] = get_noun_phrase(token)
# #             elif token.dep_ in ["dobj", "obj", "pobj", "attr", "acomp"]:
# #                 clauses[parent]["objects"].append(get_noun_phrase(token))
# #             elif token.pos_ == "AUX" and token.lemma_ not in BE_VERBS:
# #                 clauses[parent]["secondary_verbs"].append(token.lemma_.upper())
# #             elif token.dep_ == "advmod":
# #                 clauses[parent]["adverbs"].append(token.text.upper())
# #             elif token.dep_ == "neg":
# #                 clauses[parent]["negation"] = True
# #     isl_tokens = []
# #     isl_tokens.extend(interjections)
# #     isl_tokens.extend(time_expressions)
# #     sorted_clauses = sorted(clauses.items(), key=lambda item: item[0].i)
# #     for verb_token, data in sorted_clauses:
# #         if (
# #             verb_token.pos_ in ["NOUN", "PROPN"]
# #             and not data["subject"]
# #             and not data["objects"]
# #             and not data["main_verb"]
# #         ):
# #             isl_tokens.append(get_noun_phrase(verb_token))
# #             continue
# #         if data["subject"]:
# #             isl_tokens.append(data["subject"])
# #         isl_tokens.extend(data["objects"])
# #         isl_tokens.extend(data["secondary_verbs"])
# #         if data["main_verb"]:
# #             isl_tokens.append(data["main_verb"])
# #         isl_tokens.extend(data["adverbs"])
# #         if data["is_continuous"]:
# #             isl_tokens.append("CONTINUE")
# #         if data["negation"]:
# #             isl_tokens.append("NOT")
# #     if wh_word:
# #         isl_tokens.append(wh_word)
# #     final_gloss = " ".join(isl_tokens).strip()
# #     for key, value in placeholders.items():
# #         final_gloss = final_gloss.replace(key.upper(), value)
# #     if not final_gloss:
# #         fallback = [
# #             token.lemma_.upper()
# #             for token in doc
# #             if token.pos_ in ["INTJ", "NOUN", "PROPN", "ADJ"]
# #         ]
# #         fallback = " ".join(fallback)
# #         for key, value in placeholders.items():
# #             fallback = fallback.replace(key.upper(), value)
# #         return fallback
# #     return final_gloss
        
# # if __name__ == "__main__":
# #     if len(sys.argv) > 1:
# #         sentence = sys.argv[1]
# #         print(convert_to_isl(sentence))
# #     else:
# #         print("Error: No input provided.")

# # import spacy
# # import sys

# # # Load SpaCy model
# # nlp = spacy.load("en_core_web_sm")

# # WH_WORDS = {"who", "what", "where", "when", "why", "how", "which"}
# # TIME_WORDS = {"yesterday", "today", "tomorrow", "tonight", "now", "always"}
# # # 'Be' verbs should be dropped in ISL gloss
# # BE_VERBS = {"be", "is", "am", "are", "was", "were", "been", "being"}

# # Possessives become a sign placed before the noun (MY NAME).
# # Edit the right-hand side if your words.data uses different signs.
# POSSESSIVE_GLOSS = {"my": "MY", "your": "YOUR", "his": "HIS", "her": "HER",
#                     "our": "OUR", "their": "THEIR", "its": "ITS"}

# # Fixed expressions are signed as one unit and skip the grammar rules.
# FIXED_PHRASES = {
#     "good morning": "GOOD MORNING", "good afternoon": "GOOD AFTERNOON",
#     "good evening": "GOOD EVENING", "good night": "GOOD NIGHT",
#     "thank you": "THANK YOU", "thanks": "THANK YOU",
# }

# def protect_fixed_phrases(sentence, placeholders):
#     for phrase, gloss in FIXED_PHRASES.items():
#         def repl(match, gloss=gloss):
#             key = f"PLACEHOLDER{len(placeholders)}"
#             placeholders[key] = gloss
#             return key
#         sentence = re.sub(r"\b" + re.escape(phrase) + r"\b", repl, sentence, flags=re.I)
#     return sentence

# # def get_noun_phrase(token):
# #     """
# #     Extracts the noun along with its compounds and adjectives.
# #     Follows ISL Rule: [Compound] + [Noun] + [Adjective]
# #     Example: 'The big meeting room' -> 'MEETING ROOM BIG'
# #     """
# #     compounds = [child.text.upper() for child in token.children if child.dep_ == "compound"]
# #     adjectives = [child.text.upper() for child in token.children if child.dep_ in ["amod", "acomp"]]

# #     # Use lemma for standard nouns (rooms -> ROOM), but exact text for pronouns (I, IT)
# #     base_word = token.text.upper() if token.pos_ in ["PRON", "PROPN"] else token.lemma_.upper()

# #     phrase = []
# #     if compounds:
# #         phrase.extend(compounds)
# #     phrase.append(base_word)
# #     if adjectives:
# #         phrase.extend(adjectives)

# #     return " ".join(phrase)
# # def convert_to_isl(sentence):
# #     doc = nlp(sentence.lower())

# #     subject = None
# #     objects = []
# #     main_verb = None
# #     secondary_verbs = []
# #     negation = False
# #     adverbs = []
# #     time_expressions = []
# #     wh_word = None
# #     is_continuous = False
# #     interjections = [] # NEW: Capture things like "Hello", "Yes", "No"

# #     for token in doc:
# #         # 1. Interjections (Hello, Hi, Wow)
# #         if token.pos_ == "INTJ":
# #             interjections.append(token.lemma_.upper())
# #             continue

# #         # 2. Wh-Words
# #         if token.text in WH_WORDS:
# #             wh_word = token.text.upper()
# #             continue

# #         # 3. Time Words
# #         if token.text in TIME_WORDS:
# #             time_expressions.append(token.text.upper())
# #             continue

# #         # 4. Subjects
# #         if token.dep_ in ["nsubj", "nsubjpass"]:
# #             subject = get_noun_phrase(token)

# #         # 5. Objects and Complements
# #         if token.dep_ in ["dobj", "obj", "pobj", "attr", "acomp"]:
# #             objects.append(get_noun_phrase(token))

# #         # 6. Verbs
# #         if token.pos_ in ["VERB", "AUX"]:
# #             if token.lemma_ in BE_VERBS:
# #                 continue
# #             if token.tag_ == "VBG":
# #                 is_continuous = True

# #             if token.dep_ == "ROOT":
# #                 main_verb = token.lemma_.upper()
# #             elif token.dep_ != "ROOT" and token.lemma_.upper() != main_verb:
# #                 secondary_verbs.append(token.lemma_.upper())

# #         # 7. Negation
# #         if token.dep_ == "neg":
# #             negation = True

# #         # 8. Adverbs
# #         if token.pos_ == "ADV" and token.text not in TIME_WORDS and token.text not in WH_WORDS:
# #             adverbs.append(token.text.upper())

# #     # --- ASSEMBLE THE ISL GLOSS ---
# #     isl_tokens = []

# #     # Interjections usually start the sentence
# #     isl_tokens.extend(interjections)
# #     isl_tokens.extend(time_expressions)

# #     if subject:
# #         isl_tokens.append(subject)

# #     isl_tokens.extend(objects)
# #     isl_tokens.extend(secondary_verbs)

# #     if main_verb:
# #         isl_tokens.append(main_verb)

# #     if is_continuous and main_verb:
# #         isl_tokens.append("CONTINUE")

# #     if negation:
# #         isl_tokens.append("NOT")

# #     isl_tokens.extend(adverbs)

# #     if wh_word:
# #         isl_tokens.append(wh_word)

# #     final_gloss = " ".join(isl_tokens).strip()

# #     # --- NEW: THE FRAGMENT FALLBACK ---
# #     # If the sentence had no verbs or objects (like "Hello World"),
# #     # just extract the core concepts in order so it doesn't return blank.
# #     if not final_gloss:
# #         fallback = [token.lemma_.upper() for token in doc if token.pos_ in ["INTJ", "NOUN", "PROPN", "ADJ"]]
# #         return " ".join(fallback)

# #     return final_gloss

# # if __name__ == "__main__":
# #     # If a sentence is passed as a command line argument, process it and print
# #     if len(sys.argv) > 1:
# #         sentence = sys.argv[1]
# #         print(convert_to_isl(sentence))
# #     else:
# #         print("Error: No input provided.")


# import spacy
# import sys
# import re

# def protect_placeholders(sentence):
#     placeholders = {}

#     def repl(match):
#         key = f"PLACEHOLDER{len(placeholders)}"
#         placeholders[key] = match.group(0)   # Stores "[KUNAL]"
#         return key

#     protected = re.sub(r"\[[^\]]+\]", repl, sentence)
#     return protected, placeholders

# # Load SpaCy model
# nlp = spacy.load("en_core_web_sm")

# WH_WORDS = {"who", "what", "where", "when", "why", "how", "which"}
# TIME_WORDS = {"yesterday", "today", "tomorrow", "tonight", "now", "always"}
# BE_VERBS = {"be", "is", "am", "are", "was", "were", "been", "being"}

# def get_noun_phrase(token):
#     compounds = [child.text.upper() for child in token.children if child.dep_ == "compound"]
#     adjectives = [child.text.upper() for child in token.children if child.dep_ in ["amod", "acomp"]]
#     numbers = [child.text.upper() for child in token.children if child.dep_ == "nummod"]
#     possessives = [POSSESSIVE_GLOSS.get(child.text.lower(), child.text.upper())
#                    for child in token.children if child.dep_ == "poss"]
#     #base_word = token.text.upper() if token.pos_ in ["PRON", "PROPN"] else token.lemma_.upper()
#     if token.text.upper().startswith("PLACEHOLDER"):
#         base_word = token.text.upper()
#     elif token.pos_ in ["PRON", "PROPN"]:
#         base_word = token.text.upper()
#     else:
#         base_word = token.lemma_.upper()
    
#     phrase = []
#     phrase.extend(possessives)
#     if compounds:
#         phrase.extend(compounds)
#     phrase.append(base_word)
#     if adjectives:
#         phrase.extend(adjectives)
#     if numbers:
#         phrase.extend(numbers)
        
#     return " ".join(phrase)

# def convert_single(sentence):
#     sentence, placeholders = protect_placeholders(sentence)
#     sentence = protect_fixed_phrases(sentence, placeholders)
#     sentence = sentence.lower()   # consistent parsing regardless of how the user typed it
#     doc = nlp(sentence)
#     # for token in doc:
#     #     print(
#     #         token.text,
#     #         token.pos_,
#     #         token.dep_,
#     #         token.head.text
#     #     )
#     interjections = []
#     time_expressions = []
#     wh_word = None
#     # Clause buckets for handling multiple verbs sequentially: [Subject -> Object -> Verb]
#     clauses = {}

#     for token in doc:
#         if token.lemma_ == "do" and token.dep_ in ["aux", "auxpass"]:
#             continue   # English do-support (did / does / do) has no ISL sign
#         if token.pos_ in ["VERB", "AUX"] or token.dep_ == "ROOT":
#             is_be_verb = token.lemma_ in BE_VERBS
#             if is_be_verb and token.dep_ != "ROOT":
#                 continue
#             clauses[token] = {
#                 "subject": None,
#                 "objects": [],
#                 "secondary_verbs": [],
#                 "adverbs": [],
#                 "main_verb": (
#                     token.lemma_.upper()
#                     if token.pos_ in ["VERB", "AUX"] and not is_be_verb
#                     else ""
#                 ),                    
#                 # "main_verb": "" if is_be_verb else token.lemma_.upper(),
#                 "negation": False,
#                 "is_continuous": (token.tag_ == "VBG"),
#                 "maybe_objects": []
#             }
            
#         #    clauses[token] = {
#         #        "subject": None,
#         #        "objects": [],
#         #        "secondary_verbs": [],
#         #        "main_verb": "" if is_be_verb else token.lemma_.upper(),
#         #        "negation": False,
#         #        "is_continuous": (token.tag_ == "VBG")
#         #    } 
        
#     for token in doc:
#         if token.pos_ == "INTJ":
#             interjections.append(token.lemma_.upper())
#             continue
#         if token.text.lower() in WH_WORDS:
#             wh_word = token.text.upper()
#             continue
#         if token.text.lower() in TIME_WORDS:
#             time_expressions.append(token.text.upper())
#             continue
        
#         # if token.pos_ == "ADV" and token.text not in TIME_WORDS and token.text not in WH_WORDS:
#         #     adverbs.append(token.text.upper())
#         #     continue
#         # if token.pos_ == "ADV" and token.text not in TIME_WORDS and token.text not in WH_WORDS:
#         #     parent = token
#         #     while parent not in clauses:
#         #         if parent == parent.head:
#         #             break
#         #         parent = parent.head
#         #     if parent in clauses:
#         #         clauses[parent]["adverbs"].append(token.text.upper())
#         #     continue
        
#         if token in clauses:
#             continue
#         parent = token 
#         while parent not in clauses:
#             if parent == parent.head:
#                 break
#             parent = parent.head

#         # if parent in clauses:
#         #     if token.dep_ in ["nsubj", "nsubjpass"]:
#         #         clauses[parent]["subject"] = get_noun_phrase(token)
#         #     elif token.dep_ in ["dobj", "obj", "pobj", "attr", "acomp"]:
#         #         clauses[parent]["objects"].append(get_noun_phrase(token))
#         #     elif token.pos_ == "AUX" and token.lemma_ not in BE_VERBS:
#         #         clauses[parent]["secondary_verbs"].append(token.lemma_.upper())
#         #     elif token.dep_ == "neg":
#         #         clauses[parent]["negation"] = True
#         if parent in clauses:
#             if token.dep_ in ["nsubj", "nsubjpass"]:
#                 clauses[parent]["subject"] = get_noun_phrase(token)
#             elif token.dep_ in ["dobj", "obj", "pobj", "attr", "acomp", "dative"]:
#                 clauses[parent]["objects"].append(get_noun_phrase(token))
#             elif token.dep_ == "npadvmod" and token.pos_ in ["NOUN", "PROPN"]:
#                 clauses[parent]["maybe_objects"].append(get_noun_phrase(token))
#             elif token.lemma_ == "do" and token.dep_ in ["aux", "auxpass"]:
#                 pass
#             elif token.pos_ == "AUX" and token.lemma_ not in BE_VERBS:
#                 clauses[parent]["secondary_verbs"].append(token.lemma_.upper())
#             elif token.dep_ == "advmod":
#                 clauses[parent]["adverbs"].append(token.text.upper())
#             elif token.dep_ == "neg":
#                 clauses[parent]["negation"] = True
#     isl_tokens = []
#     isl_tokens.extend(interjections)
#     isl_tokens.extend(time_expressions)
#     sorted_clauses = sorted(clauses.items(), key=lambda item: item[0].i)
#     for verb_token, data in sorted_clauses:
#         if (
#             verb_token.pos_ in ["NOUN", "PROPN"]
#             and not data["subject"]
#             and not data["objects"]
#             and not data["main_verb"]
#         ):
#             isl_tokens.append(get_noun_phrase(verb_token))
#             continue
#         if data["subject"]:
#             isl_tokens.append(data["subject"])
#         isl_tokens.extend(data["objects"] or data["maybe_objects"])
#         isl_tokens.extend(data["secondary_verbs"])
#         if data["main_verb"]:
#             isl_tokens.append(data["main_verb"])
#         isl_tokens.extend(data["adverbs"])
#         if data["is_continuous"]:
#             isl_tokens.append("CONTINUE")
#         if data["negation"]:
#             isl_tokens.append("NOT")
#     if wh_word:
#         isl_tokens.append(wh_word)
#     final_gloss = " ".join(isl_tokens).strip()
#     for key, value in placeholders.items():
#         final_gloss = final_gloss.replace(key.upper(), value)
#     if not final_gloss:
#         fallback = [
#             token.lemma_.upper()
#             for token in doc
#             if token.pos_ in ["INTJ", "NOUN", "PROPN", "ADJ"]
#         ]
#         fallback = " ".join(fallback)
#         for key, value in placeholders.items():
#             fallback = fallback.replace(key.upper(), value)
#         return fallback
#     return final_gloss

# SEQ_RE = re.compile(r"\s*[,.;]?\s*\b(?:and then|after that|afterwards|then)\b\s*,?\s*", re.I)

# def _find_subject(clause_text):
#     """Return the subject of a clause as it should be re-used (or None)."""
#     protected, ph = protect_placeholders(clause_text)
#     for t in nlp(protected.lower()):
#         if t.dep_ in ("nsubj", "nsubjpass") and t.pos_ in ("PRON", "PROPN", "NOUN"):
#             return ph.get(t.text.upper(), t.text)
#     return None

# def _drop_first(gloss, word):
#     tokens = gloss.split()
#     target = word.upper()
#     if target in tokens:
#         tokens.remove(target)
#     return " ".join(tokens)

# def convert_to_isl(sentence):
#     """Split at sequence words (then / and then / after that), parse each clause on its own,
#     copy the previous subject into a subject-less clause, and join the glosses with THEN."""
#     parts = [p.strip() for p in SEQ_RE.split(sentence) if p.strip()]
#     if len(parts) <= 1:
#         return convert_single(parts[0] if parts else sentence)
#     glosses, carried = [], None
#     for part in parts:
#         subj = _find_subject(part)
#         text, dropped = part, None
#         if subj is None and carried:
#             text, dropped = f"{carried} {part}", carried
#         g = convert_single(text)
#         if dropped:
#             g = _drop_first(g, dropped)
#         if subj:
#             carried = subj
#         if g:
#             glosses.append(g)
#     return " THEN ".join(glosses)

# if __name__ == "__main__":
#     if len(sys.argv) > 1:
#         sentence = sys.argv[1]
#         print(convert_to_isl(sentence))
#     else:
#         print("Error: No input provided.")

# import spacy
# import sys

# # Load SpaCy model
# nlp = spacy.load("en_core_web_sm")

# WH_WORDS = {"who", "what", "where", "when", "why", "how", "which"}
# TIME_WORDS = {"yesterday", "today", "tomorrow", "tonight", "now", "always"}
# # 'Be' verbs should be dropped in ISL gloss
# BE_VERBS = {"be", "is", "am", "are", "was", "were", "been", "being"}
# Time-of-day / period nouns are treated like time words (moved to the front)
TIME_NOUNS = {"morning", "afternoon", "evening", "night", "week", "month", "year", "day", "weekend"}

# Possessives become a sign placed before the noun (MY NAME).
# Edit the right-hand side if your words.data uses different signs.
POSSESSIVE_GLOSS = {"my": "MY", "your": "YOUR", "his": "HIS", "her": "HER",
                    "our": "OUR", "their": "THEIR", "its": "ITS"}

# Fixed expressions are signed as one unit and skip the grammar rules.
FIXED_PHRASES = {
    "good morning": "GOOD MORNING", "good afternoon": "GOOD AFTERNOON",
    "good evening": "GOOD EVENING", "good night": "GOOD NIGHT",
    "thank you": "THANK YOU", "thanks": "THANK YOU",
}

def protect_fixed_phrases(sentence, placeholders):
    for phrase, gloss in FIXED_PHRASES.items():
        def repl(match, gloss=gloss):
            key = f"PLACEHOLDER{len(placeholders)}"
            placeholders[key] = gloss
            return key
        sentence = re.sub(r"\b" + re.escape(phrase) + r"\b", repl, sentence, flags=re.I)
    return sentence

# def get_noun_phrase(token):
#     """
#     Extracts the noun along with its compounds and adjectives.
#     Follows ISL Rule: [Compound] + [Noun] + [Adjective]
#     Example: 'The big meeting room' -> 'MEETING ROOM BIG'
#     """
#     compounds = [child.text.upper() for child in token.children if child.dep_ == "compound"]
#     adjectives = [child.text.upper() for child in token.children if child.dep_ in ["amod", "acomp"]]

#     # Use lemma for standard nouns (rooms -> ROOM), but exact text for pronouns (I, IT)
#     base_word = token.text.upper() if token.pos_ in ["PRON", "PROPN"] else token.lemma_.upper()

#     phrase = []
#     if compounds:
#         phrase.extend(compounds)
#     phrase.append(base_word)
#     if adjectives:
#         phrase.extend(adjectives)

#     return " ".join(phrase)
# def convert_to_isl(sentence):
#     doc = nlp(sentence.lower())

#     subject = None
#     objects = []
#     main_verb = None
#     secondary_verbs = []
#     negation = False
#     adverbs = []
#     time_expressions = []
#     wh_word = None
#     is_continuous = False
#     interjections = [] # NEW: Capture things like "Hello", "Yes", "No"

#     for token in doc:
#         # 1. Interjections (Hello, Hi, Wow)
#         if token.pos_ == "INTJ":
#             interjections.append(token.lemma_.upper())
#             continue

#         # 2. Wh-Words
#         if token.text in WH_WORDS:
#             wh_word = token.text.upper()
#             continue

#         # 3. Time Words
#         if token.text in TIME_WORDS:
#             time_expressions.append(token.text.upper())
#             continue

#         # 4. Subjects
#         if token.dep_ in ["nsubj", "nsubjpass"]:
#             subject = get_noun_phrase(token)

#         # 5. Objects and Complements
#         if token.dep_ in ["dobj", "obj", "pobj", "attr", "acomp"]:
#             objects.append(get_noun_phrase(token))

#         # 6. Verbs
#         if token.pos_ in ["VERB", "AUX"]:
#             if token.lemma_ in BE_VERBS:
#                 continue
#             if token.tag_ == "VBG":
#                 is_continuous = True

#             if token.dep_ == "ROOT":
#                 main_verb = token.lemma_.upper()
#             elif token.dep_ != "ROOT" and token.lemma_.upper() != main_verb:
#                 secondary_verbs.append(token.lemma_.upper())

#         # 7. Negation
#         if token.dep_ == "neg":
#             negation = True

#         # 8. Adverbs
#         if token.pos_ == "ADV" and token.text not in TIME_WORDS and token.text not in WH_WORDS:
#             adverbs.append(token.text.upper())

#     # --- ASSEMBLE THE ISL GLOSS ---
#     isl_tokens = []

#     # Interjections usually start the sentence
#     isl_tokens.extend(interjections)
#     isl_tokens.extend(time_expressions)

#     if subject:
#         isl_tokens.append(subject)

#     isl_tokens.extend(objects)
#     isl_tokens.extend(secondary_verbs)

#     if main_verb:
#         isl_tokens.append(main_verb)

#     if is_continuous and main_verb:
#         isl_tokens.append("CONTINUE")

#     if negation:
#         isl_tokens.append("NOT")

#     isl_tokens.extend(adverbs)

#     if wh_word:
#         isl_tokens.append(wh_word)

#     final_gloss = " ".join(isl_tokens).strip()

#     # --- NEW: THE FRAGMENT FALLBACK ---
#     # If the sentence had no verbs or objects (like "Hello World"),
#     # just extract the core concepts in order so it doesn't return blank.
#     if not final_gloss:
#         fallback = [token.lemma_.upper() for token in doc if token.pos_ in ["INTJ", "NOUN", "PROPN", "ADJ"]]
#         return " ".join(fallback)

#     return final_gloss

# if __name__ == "__main__":
#     # If a sentence is passed as a command line argument, process it and print
#     if len(sys.argv) > 1:
#         sentence = sys.argv[1]
#         print(convert_to_isl(sentence))
#     else:
#         print("Error: No input provided.")


import spacy
import sys
import re

def protect_placeholders(sentence):
    placeholders = {}

    def repl(match):
        key = f"PLACEHOLDER{len(placeholders)}"
        placeholders[key] = match.group(0)   # Stores "[KUNAL]"
        return key

    protected = re.sub(r"\[[^\]]+\]", repl, sentence)
    return protected, placeholders

# Load SpaCy model
nlp = spacy.load("en_core_web_sm")

WH_WORDS = {"who", "what", "where", "when", "why", "how", "which"}
TIME_WORDS = {"yesterday", "today", "tomorrow", "tonight", "now", "always"}
BE_VERBS = {"be", "is", "am", "are", "was", "were", "been", "being"}

def get_noun_phrase(token):
    compounds = [child.text.upper() for child in token.children if child.dep_ == "compound"]
    adjectives = [child.text.upper() for child in token.children if child.dep_ in ["amod", "acomp"]]
    numbers = [child.text.upper() for child in token.children if child.dep_ == "nummod"]
    possessives = [POSSESSIVE_GLOSS.get(child.text.lower(), child.text.upper())
                   for child in token.children if child.dep_ == "poss"]
    #base_word = token.text.upper() if token.pos_ in ["PRON", "PROPN"] else token.lemma_.upper()
    if token.text.upper().startswith("PLACEHOLDER"):
        base_word = token.text.upper()
    elif token.pos_ in ["PRON", "PROPN"]:
        base_word = token.text.upper()
    else:
        base_word = token.lemma_.upper()
    
    phrase = []
    phrase.extend(possessives)
    if compounds:
        phrase.extend(compounds)
    phrase.append(base_word)
    if adjectives:
        phrase.extend(adjectives)
    if numbers:
        phrase.extend(numbers)
        
    return " ".join(phrase)

def convert_single(sentence):
    sentence, placeholders = protect_placeholders(sentence)
    sentence = protect_fixed_phrases(sentence, placeholders)
    sentence = sentence.lower()   # consistent parsing regardless of how the user typed it
    doc = nlp(sentence)
    # for token in doc:
    #     print(
    #         token.text,
    #         token.pos_,
    #         token.dep_,
    #         token.head.text
    #     )
    interjections = []
    time_expressions = []
    wh_word = None
    # Clause buckets for handling multiple verbs sequentially: [Subject -> Object -> Verb]
    clauses = {}

    for token in doc:
        if token.lemma_ == "do" and token.dep_ in ["aux", "auxpass"]:
            continue   # English do-support (did / does / do) has no ISL sign
        if token.pos_ in ["VERB", "AUX"] or token.dep_ == "ROOT":
            is_be_verb = token.lemma_ in BE_VERBS
            if is_be_verb and token.dep_ != "ROOT":
                continue
            clauses[token] = {
                "subject": None,
                "objects": [],
                "secondary_verbs": [],
                "adverbs": [],
                "main_verb": (
                    token.lemma_.upper()
                    if token.pos_ in ["VERB", "AUX"] and not is_be_verb
                    else ""
                ),                    
                # "main_verb": "" if is_be_verb else token.lemma_.upper(),
                "negation": False,
                "is_continuous": (token.tag_ == "VBG"),
                "maybe_objects": []
            }
            
        #    clauses[token] = {
        #        "subject": None,
        #        "objects": [],
        #        "secondary_verbs": [],
        #        "main_verb": "" if is_be_verb else token.lemma_.upper(),
        #        "negation": False,
        #        "is_continuous": (token.tag_ == "VBG")
        #    } 
        
    for token in doc:
        if token.pos_ == "INTJ":
            interjections.append(token.lemma_.upper())
            continue
        if token.text.lower() in WH_WORDS:
            wh_word = token.text.upper()
            continue
        if token.text.lower() in TIME_WORDS:
            time_expressions.append(token.text.upper())
            continue
        if (token.lemma_ in TIME_NOUNS
                and token.dep_ not in ["nsubj", "nsubjpass", "dobj", "obj", "attr", "acomp", "ROOT"]
                and token not in clauses):
            mods = [c.text.upper() for c in token.children if c.text.lower() in ("last", "next", "every")]
            time_expressions.extend(mods + [token.lemma_.upper()])
            continue
        
        # if token.pos_ == "ADV" and token.text not in TIME_WORDS and token.text not in WH_WORDS:
        #     adverbs.append(token.text.upper())
        #     continue
        # if token.pos_ == "ADV" and token.text not in TIME_WORDS and token.text not in WH_WORDS:
        #     parent = token
        #     while parent not in clauses:
        #         if parent == parent.head:
        #             break
        #         parent = parent.head
        #     if parent in clauses:
        #         clauses[parent]["adverbs"].append(token.text.upper())
        #     continue
        
        if token in clauses:
            continue
        parent = token 
        while parent not in clauses:
            if parent == parent.head:
                break
            parent = parent.head

        # if parent in clauses:
        #     if token.dep_ in ["nsubj", "nsubjpass"]:
        #         clauses[parent]["subject"] = get_noun_phrase(token)
        #     elif token.dep_ in ["dobj", "obj", "pobj", "attr", "acomp"]:
        #         clauses[parent]["objects"].append(get_noun_phrase(token))
        #     elif token.pos_ == "AUX" and token.lemma_ not in BE_VERBS:
        #         clauses[parent]["secondary_verbs"].append(token.lemma_.upper())
        #     elif token.dep_ == "neg":
        #         clauses[parent]["negation"] = True
        if parent in clauses:
            if token.dep_ in ["nsubj", "nsubjpass"]:
                clauses[parent]["subject"] = get_noun_phrase(token)
            elif token.dep_ in ["dobj", "obj", "pobj", "attr", "acomp", "dative"]:
                clauses[parent]["objects"].append(get_noun_phrase(token))
            elif token.dep_ == "npadvmod" and token.pos_ in ["NOUN", "PROPN"]:
                clauses[parent]["maybe_objects"].append(get_noun_phrase(token))
            elif token.lemma_ == "do" and token.dep_ in ["aux", "auxpass"]:
                pass
            elif token.pos_ == "AUX" and token.lemma_ not in BE_VERBS:
                clauses[parent]["secondary_verbs"].append(token.lemma_.upper())
            elif token.dep_ == "advmod":
                clauses[parent]["adverbs"].append(token.text.upper())
            elif token.dep_ == "neg":
                clauses[parent]["negation"] = True
    isl_tokens = []
    isl_tokens.extend(interjections)
    isl_tokens.extend(time_expressions)
    sorted_clauses = sorted(clauses.items(), key=lambda item: item[0].i)
    for verb_token, data in sorted_clauses:
        if (
            verb_token.pos_ in ["NOUN", "PROPN"]
            and not data["subject"]
            and not data["objects"]
            and not data["main_verb"]
        ):
            isl_tokens.append(get_noun_phrase(verb_token))
            continue
        if data["subject"]:
            isl_tokens.append(data["subject"])
        isl_tokens.extend(data["objects"] or data["maybe_objects"])
        isl_tokens.extend(data["secondary_verbs"])
        if data["main_verb"]:
            isl_tokens.append(data["main_verb"])
        isl_tokens.extend(data["adverbs"])
        if data["is_continuous"]:
            isl_tokens.append("CONTINUE")
        if data["negation"]:
            isl_tokens.append("NOT")
    if wh_word:
        isl_tokens.append(wh_word)
    final_gloss = " ".join(isl_tokens).strip()
    for key, value in placeholders.items():
        final_gloss = final_gloss.replace(key.upper(), value)
    if not final_gloss:
        fallback = [
            token.lemma_.upper()
            for token in doc
            if token.pos_ in ["INTJ", "NOUN", "PROPN", "ADJ"]
        ]
        fallback = " ".join(fallback)
        for key, value in placeholders.items():
            fallback = fallback.replace(key.upper(), value)
        return fallback
    return final_gloss

SEQ_RE = re.compile(r"\s*[,.;]?\s*\b(?:and then|after that|afterwards|then)\b\s*,?\s*", re.I)

def _find_subject(clause_text):
    """Return the subject of a clause as it should be re-used (or None)."""
    protected, ph = protect_placeholders(clause_text)
    for t in nlp(protected.lower()):
        if t.dep_ in ("nsubj", "nsubjpass") and t.pos_ in ("PRON", "PROPN", "NOUN"):
            return ph.get(t.text.upper(), t.text)
    return None

def _drop_first(gloss, word):
    tokens = gloss.split()
    target = word.upper()
    if target in tokens:
        tokens.remove(target)
    return " ".join(tokens)

def convert_to_isl(sentence):
    """Split at sequence words (then / and then / after that), parse each clause on its own,
    copy the previous subject into a subject-less clause, and join the glosses with THEN."""
    parts = [p.strip() for p in SEQ_RE.split(sentence) if p.strip()]
    if len(parts) <= 1:
        return convert_single(parts[0] if parts else sentence)
    glosses, carried = [], None
    for part in parts:
        subj = _find_subject(part)
        text, dropped = part, None
        if subj is None and carried:
            text, dropped = f"{carried} {part}", carried
        g = convert_single(text)
        if dropped:
            g = _drop_first(g, dropped)
        if subj:
            carried = subj
        if g:
            glosses.append(g)
    return " THEN ".join(glosses)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sentence = sys.argv[1]
        print(convert_to_isl(sentence))
    else:
        print("Error: No input provided.")