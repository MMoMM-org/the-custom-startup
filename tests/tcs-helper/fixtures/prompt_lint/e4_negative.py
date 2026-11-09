"""Prompt strings whose interpolation is delimited, and strings that are not prompts."""
import os
import subprocess


def summarise(text):
    prompt = f"Summarise the text in the tags.\n<input>\n{text}\n</input>"
    return prompt


def fenced(diff):
    instructions = "Review the diff below.\n```diff\n{}\n```".format(diff)
    return instructions


def plain(name):
    message = f"hello {name}"
    label = "user: %s" % name
    prompt_header = "Answer in one line."
    subprocess.run(["git", "log", f"--author={name}"])
    return message, label, prompt_header


def paths(name, items):
    # Prompt-ish words that are not a prompt: a path-like suffix segment, a
    # longer word containing "system", or a literal that is not text.
    system_path = f"{os.getcwd()}/x"
    prompt_file = "/tmp/{}.md".format(name)
    filesystem_root = f"Root of the tree for {name}"
    instruction_count = "%d instructions in the file" % len(items)
    prompt_key = f"{name}/{name}"
    return system_path, prompt_file, filesystem_root, instruction_count, prompt_key
