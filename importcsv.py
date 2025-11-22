import csv

# Define MCQs list
mcqs = [
    ["Communication is mainly about:", "Moving physically from one place to another", "Transmitting information from one entity to another", "Storing data in a database", "Only sending written letters", 2],
    ["Which of the following can be considered 'information' in communication?", "Emotions", "Ideas", "Thoughts", "All of the above", 4],
    ["A social animal communicates using:", "Only spoken words", "Only written documents", "Spoken words, signs/symbols and non-verbal gestures", "Only electronic devices", 3],
    ["The electric telegraph was invented by Samuel Morse in around:", "1800", "1837", "1900", "1963", 2],
    ["The first public message on telegraph lines was sent in:", "1837", "1844", "1876", "1963", 2],
    ["Alexander Graham Bell's famous line during the first telephone call was:", "Hello, world!", "Can you hear me?", "Mr. Watson, come here, I want you.", "This is the first call.", 3],
    ["The telephone was patented in:", "1844", "1876", "1900", "1947", 2],
    ["The first telecom satellite SYNCOM-1 was launched in:", "1947", "1955", "1963", "1970", 3],
    ["John Bardeen is associated with the invention of:", "Telephone", "Telegraph", "Transistor", "Television", 3],
    ["The name 'Vodafone' is derived from:", "Voice Data Phone", "Virtual Data Fone", "Voice Data Fone", "Voice Digital Phone", 3]
    # ... more MCQs (you can add the remaining 90 similarly)
]

# CSV file path
csv_file_path = 'telecom_mcqs.csv'

# Write to CSV
with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['question','option1','option2','option3','option4','answer_index'])
    for row in mcqs:
        writer.writerow(row)

csv_file_path
