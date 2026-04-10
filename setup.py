from setuptools import setup

setup(
    name="cli-anything-moodle",
    version="1.0.0",
    description="CLI harness for Moodle LMS — agent-native interface to courses, assignments, grades, calendar, messages, and more.",
    author="EROnomist",
    py_modules=["cli_moodle"],
    install_requires=["click>=8.0", "requests"],
    entry_points={
        "console_scripts": [
            "moodle=cli_moodle:cli",
        ],
    },
    python_requires=">=3.10",
)
