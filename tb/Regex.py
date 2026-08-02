import re
pattern = r"[a-zA-Z0-9]+@[a-zA-Z]+\.(com|net|edu)"

user_input = input()

if(re.search(pattern, user_input)):
    print("valid email!")
else:
    print("invalid email")