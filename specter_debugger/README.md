<a id="readme-top"></a>

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![project_license][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/AdamMinge/specter_client">
    <img src="../images/logo.png" alt="Logo" width="80" height="80">
  </a>

<h3 align="center">Specter Debugger</h3>

  <p align="center">
    Specter Debugger is a command-line-oriented module used to run scripted automation scenarios against Specter targets. Useful for continuous integration, regression testing, and interactive debugging.
    </br>
    </br>
    <a href="https://github.com/AdamMinge/specter_client"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/AdamMinge/specter_client">View Demo</a>
    &middot;
    <a href="https://github.com/AdamMinge/specter_client/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    &middot;
    <a href="https://github.com/AdamMinge/specter_client/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#about">About</a></li>
    <li><a href="#usage">Usage</a></li>
      <ol>
        <li><a href="#server-mode">Server Mode</a></li>
        <li><a href="#client-mode">Client Mode</a></li>
      </ol>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

<!-- ABOUT -->
## About

The Specter Debugger provides a simple gRPC-based debugging server and client for running and inspecting Python code remotely.
It comes with two main modes:

- Server Mode — runs the debugger server that can be connected to.
- Client Mode — connects to a running debugger server and provides an interactive CLI to manage sessions, sources, breakpoints, and listen to debug events.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE -->
## Usage

Run the CLI using:
```sh
specter_debugger [MODE] [OPTIONS]
```

Where [MODE] is either:
- server — start the debugger server
- client — connect to an existing debugger server

<!-- SERVER MODE -->
### Server Mode

#### Command
```sh
specter_debugger server [OPTIONS]
```

| Option        | Default     | Description                                                  |
| ------------- | ----------- | ------------------------------------------------------------ |
| `--host`      | `localhost` | Host address to bind the server                              |
| `--port`      | `50051`     | Port to bind the server                                      |
| `--autostart` | *off*       | Automatically start the server without waiting for CLI input |

#### Server Commands (interactive mode)

Once in server mode (if --autostart is not provided), you can run:
| Command | Description                           |
| ------- | ------------------------------------- |
| `start` | Start the gRPC debugger server        |
| `stop`  | Stop the gRPC debugger server         |
| `exit`  | Stop the server (if running) and exit |
| `help`  | Show help                             |

<!-- CLIENT MODE -->
### Client Mode

#### Command
```sh
specter_debugger client [OPTIONS]
```

| Option   | Default     | Description                      |
| -------- | ----------- | -------------------------------- |
| `--host` | `localhost` | Host of the server to connect to |
| `--port` | `50051`     | Port of the server to connect to |

#### Client Commands (interactive mode)

Once in client mode, you have access to:
| Command                         | Usage                          | Description                                  |
| ------------------------------- | ------------------------------ | -------------------------------------------- |
| `create_session`                |                                | Create a new debugging session               |
| `get_sessions`                  |                                | List active sessions                         |
| `set_source <filename>`         | `set_source main.py`           | Upload a source file to the current session  |
| `start`                         |                                | Start debugging the current session          |
| `stop`                          |                                | Stop debugging the current session           |
| `add_breakpoint <file:line>`    | `add_breakpoint main.py:10`    | Add a breakpoint                             |
| `remove_breakpoint <file:line>` | `remove_breakpoint main.py:10` | Remove a breakpoint                          |
| `get_breakpoints`               |                                | List all breakpoints for the current session |
| `listen`                        |                                | Start listening to debug events (async)      |
| `stop_listen`                   |                                | Stop listening to events                     |
| `exit`                          |                                | Exit the client                              |
| `help`                          |                                | Show help                                    |

#### Event Listening

When listen is enabled, the client will display real-time debug events:
- Line change → [EVENT] Line changed: file.py:42
- Session finish → [EVENT] Debug session finished
- Standard output → [STDOUT] message
- Standard error → [STDERR] message


<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ROADMAP -->
## Roadmap

See the [open issues](https://github.com/AdamMinge/specter_client/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->
## Contact

Adam Minge - minge.adam@gmail.com

Project Link: [https://github.com/AdamMinge/specter_client](https://github.com/AdamMinge/specter_client)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/AdamMinge/specter_client.svg?style=for-the-badge
[contributors-url]: https://github.com/AdamMinge/specter_client/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/AdamMinge/specter_client.svg?style=for-the-badge
[forks-url]: https://github.com/AdamMinge/specter_client/network/members
[stars-shield]: https://img.shields.io/github/stars/AdamMinge/specter_client.svg?style=for-the-badge
[stars-url]: https://github.com/AdamMinge/specter_client/stargazers
[issues-shield]: https://img.shields.io/github/issues/AdamMinge/specter_client.svg?style=for-the-badge
[issues-url]: https://github.com/AdamMinge/specter_client/issues
[license-shield]: https://img.shields.io/github/license/AdamMinge/specter_client.svg?style=for-the-badge
[license-url]: https://github.com/AdamMinge/specter_client/blob/master/LICENSE.txt
[Python]: https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white
[Python-url]: https://www.python.org/
[Poetry]: https://img.shields.io/badge/Poetry-1.8+-blueviolet?logo=python&logoColor=white
[Poetry-url]: https://python-poetry.org/
[PySide6]: https://img.shields.io/badge/PySide6-6.9+-green?logo=qt&logoColor=white
[PySide6-url]: https://doc.qt.io/qtforpython-6/index.html