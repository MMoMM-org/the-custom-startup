"""Prompt strings that interpolate input without a delimiter."""
import subprocess


def summarise(text):
    prompt = f'Summarise this text: "{text}"'
    return prompt


def ask(client, question):
    return client.create(
        system="You answer questions about {}.".format(question),
        messages=[{"role": "user", "content": "Question: %s" % question}],
    )


def run_cli(entry):
    subprocess.run(["claude", "-p", "Classify: " + entry + f" ({entry})"])


def legacy(name):
    system_text = "Hello {name}, review the diff."
    return system_text.format(name=name)
