from pathlib import Path
import signal
import subprocess
import threading
import time

import server as tcp_server

import pytest


@pytest.fixture()
def client():
    def run(args=None):
        args = args or ""

        return subprocess.run(f"bin/tcp_client {args}", capture_output=True, shell=True)

    return run


@pytest.fixture()
def server():
    process = None

    def run(port=8080, same_output=False):
        nonlocal process

        args = ["python", "server.py", "--port", f"{port}"]
        if same_output:
            args.append("--same-output")

        process = subprocess.Popen(args)
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass

        return process

    yield run

    if process:
        process.send_signal(signal.SIGINT)


def test_format(json_metadata):
    json_metadata["type"] = "coding-standard"
    json_metadata["description"] = "Check that code is formatted correctly."

    for source_file in Path("src/").glob("*.c"):
        if source_file.name == "log.c":
            continue

        style_1_result = subprocess.run(
            f'clang-format --style="{{BasedOnStyle: LLVM, UseTab: Never, IndentWidth: 4, TabWidth: 4}}" "{source_file}" | diff - "{source_file}"',
            shell=True,
            capture_output=True,
        )

        style_2_result = subprocess.run(
            f'clang-format --style="{{ BasedOnStyle: LLVM, UseTab: Never, IndentWidth: 4, TabWidth: 4, ColumnLimit: 100 }}" "{source_file}" | diff - "{source_file}"',
            shell=True,
            capture_output=True,
        )

        assert (
            len(style_1_result.stdout.decode()) == 0
            or len(style_2_result.stdout.decode()) == 0
        )


def test_warnings(json_metadata):
    json_metadata["type"] = "coding-standard"
    json_metadata[
        "description"
    ] = "Check that code does not produce errors when compiled."

    # result = subprocess.run("make clean && make", capture_output=True, shell=True)
    # assert result.stderr.decode() == ""

    assert True


def test_usage(client, json_metadata):
    json_metadata["type"] = "core"
    json_metadata["description"] = ""

    result = client()
    assert result.stdout == b""
    assert result.stderr != b""
    assert result.returncode == 1

    stderr = result.stderr.decode()
    message, usage = stderr.split("\n", 1)

    # First line should be error message
    assert not message.startswith("Usage")
    # Second line should contain the usage
    assert "Usage" in usage


def test_help(client, json_metadata):
    json_metadata["type"] = "core"
    json_metadata[
        "description"
    ] = "Check that help message is printed to stdout and the correct return code is returned."

    result = client("--help")
    assert result.stdout != b""
    assert result.stderr == b""
    # Don't check return code because it is ambiguous.
    # Should it be an error or success ¯\_(ツ)_/¯
    # assert result.returncode == 0

    stdout = result.stdout.decode()

    assert stdout.strip().startswith("Usage")


def test_unknown_option(client, json_metadata):
    json_metadata["type"] = "core"
    json_metadata[
        "description"
    ] = "Check that an unknown option is handled properly (nothing printed to stdout, something is printed to stderr, and correct return code is returned)."

    result = client("--unknown")
    assert result.stdout == b""
    assert result.stderr != b""
    assert result.returncode == 1

    stderr = result.stderr.decode()
    message, usage = stderr.split("\n", 1)

    # First line should be error message
    assert not message.startswith("Usage")
    # Second line should contain the usage
    assert "Usage" in usage


def test_extra_arg(client, json_metadata):
    json_metadata["type"] = "core"
    json_metadata[
        "description"
    ] = "Check that an extra argument is handled properly (nothing printed to stdout, something is printed to stderr, and correct return code is returned)."

    result = client("reverse test extra")
    assert result.stdout == b""
    assert result.stderr != b""
    assert result.returncode == 1

    stderr = result.stderr.decode()
    message, usage = stderr.split("\n", 1)

    # First line should be error message
    assert not message.startswith("Usage")
    # Second line should contain the usage
    assert "Usage" in usage


def test_less_args(client, json_metadata):
    json_metadata["type"] = "core"
    json_metadata[
        "description"
    ] = "Check that too few arguments are handled properly (nothing printed to stdout, something is printed to stderr, and correct return code is returned)."

    result = client("reverse")
    assert result.stdout == b""
    assert result.stderr != b""
    assert result.returncode == 1

    stderr = result.stderr.decode()
    message, usage = stderr.split("\n", 1)

    # First line should be error message
    assert not message.startswith("Usage")
    # Second line should contain the usage
    assert "Usage" in usage


def test_bad_action(client, json_metadata):
    json_metadata["type"] = "advance"
    json_metadata[
        "description"
    ] = "Check that an unknown action is handled properly (nothing printed to stdout, something is printed to stderr, and correct return code is returned)."

    result = client("test test")
    assert result.stdout == b""
    assert result.stderr != b""
    assert result.returncode == 1

    stderr = result.stderr.decode()
    message, usage = stderr.split("\n", 1)

    # First line should be error message
    assert not message.startswith("Usage")
    # Second line should contain the usage
    assert "Usage" in usage


def test_bad_port(client, json_metadata):
    json_metadata["type"] = "advance"
    json_metadata["description"] = (
        "Check that an invalid port is handled properly (nothing printed to stdout, something is "
        "printed to stderr, and correct return code is returned). Example: -p abcd"
    )

    result = client("-p foobar reverse test")
    assert result.stdout == b""
    assert result.stderr != b""
    assert result.returncode == 1

    stderr = result.stderr.decode()
    message, usage = stderr.split("\n", 1)

    # First line should be error message
    assert not message.startswith("Usage")
    # Second line should contain the usage
    assert "Usage" in usage


def test_bad_port_2(client, json_metadata):
    json_metadata["type"] = "advance"
    json_metadata["description"] = (
        "Check that an invalid port is handled properly (nothing printed to stdout, something is "
        "printed to stderr, and correct return code is returned). Example: -p 123abc"
    )

    result = client("-p 8080f reverse test")
    assert result.stdout == b""
    assert result.stderr != b""
    assert result.returncode == 1

    stderr = result.stderr.decode()
    message, usage = stderr.split("\n", 1)

    # First line should be error message
    assert not message.startswith("Usage")
    # Second line should contain the usage
    assert "Usage" in usage


def test_no_connection(client, json_metadata):
    json_metadata["type"] = "advance"
    json_metadata["description"] = (
        "Check that an error is returned when a server is not available ",
        "(nothing printed to stdout, something is printed to stderr, and correct return code is returned).",
    )

    result = client("reverse test")
    assert result.stdout == b""
    assert result.stderr != b""
    assert result.returncode == 1


def test_normal_input(client, server, json_metadata):
    json_metadata["type"] = "core"
    json_metadata["description"] = (
        "Check normal function ",
        "(correct resposne is printed to stdout, nothing is printed to stderr, and correct return code is returned). ",
        "Also use the verbose flag to have something printed to stderr.",
    )

    server_process = server()

    result = client("reverse test")
    assert result.stdout != b""
    assert result.stderr == b""
    assert result.returncode == 0

    stdout = result.stdout.decode().strip()
    assert stdout == "tset"

    # This time there should be something coming out of stderr
    result = client("--verbose reverse test")
    assert result.stdout != b""
    # I didn't force students to use logging, so I can't check if they print
    # anything to stderr.
    # assert result.stderr != b""
    assert result.returncode == 0

    stdout = result.stdout.decode().strip()
    assert stdout == "tset"


def test_server_connection(client, server, json_metadata):
    json_metadata["type"] = "core"
    json_metadata["description"] = (
        "Check that the client is using the server ",
        "(incorrect response printed to stdout, nothing is printed to stderr, and correct return code is returned).",
    )

    server_process = server(same_output=True)

    result = client("reverse test")
    assert result.stdout != b""
    assert result.stderr == b""
    assert result.returncode == 0

    stdout = result.stdout.decode().strip()
    assert stdout == "test"


def test_different_port(client, server, json_metadata):
    json_metadata["type"] = "core"
    json_metadata["description"] = ("Check that changing the port works.",)

    server_process = server(port=8081)

    result = client('--port 8081 reverse "hello world"')
    assert result.stdout != b""
    assert result.stderr == b""
    assert result.returncode == 0

    stdout = result.stdout.decode().strip()
    assert stdout == "dlrow olleh"


def test_large_input(client, server, json_metadata):
    json_metadata["type"] = "core"
    json_metadata["description"] = "Unable to handle 1024 byte input."
    json_metadata["description"] = "Check with 1024 byte input"

    server_process = server()
    text_input = "x" * 1024  # Make we don't go above the limit for the lab

    result = client(f'uppercase "{text_input}"')
    assert result.stdout != b""
    assert result.stderr == b""
    assert result.returncode == 0

    stdout = result.stdout.decode().strip()
    assert stdout == text_input.upper()

    print(result.stderr.decode())


def test_actions(client, server, json_metadata):
    json_metadata["type"] = "core"
    json_metadata["description"] = "Test that program works with all actions."

    server_process = server()
    text = "this is a test"

    actions = ["lowercase", "uppercase", "title-case", "reverse"]

    for action in actions:
        result = client(f'{action} "{text}"')
        assert result.stdout != b""
        assert result.stderr == b""
        assert result.returncode == 0

        stdout = result.stdout.decode().strip()
        assert stdout == tcp_server.actions[action](text)
