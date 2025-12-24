def strip_between_chars(input_string, start_char, end_char):
    start_index = input_string.find(start_char)

    if start_index != -1:
        end_index = input_string.find(end_char, start_index + 1)
    else:
        return input_string

    if end_index != -1:
        new_string = input_string[:start_index] + input_string[end_index + 1:]
        return new_string
    else:
        return input_string