"""Prompt strings whose interpolation is delimited, and strings that are not prompts."""
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
