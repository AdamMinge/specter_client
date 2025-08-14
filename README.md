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
    <img src="images/logo.png" alt="Logo" width="80" height="80">
  </a>

<h3 align="center">Specter</h3>

  <p align="center">
    Specter is a Python package composed of three core modules that together support testing automation, inspection, and scripting of target applications.
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
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#build-modules">Build Modules</a></li>
        <li><a href="#deploy-modules">Deploy Modules</a></li>
      </ul>
    </li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About The Project

specter_client is modular toolkit for interacting with Qt applications instrumented by the Specter DLL.



- <a href="/specter/README.md"><strong>Specter</strong></a> - 
Core client and scripting engine. Provides the low-level API for connecting to and communicating with Specter-instrumented Qt applications over gRPC. Enables scripting, test automation, and programmatic interaction.

- <a href="/specter_viewer/README.md"><strong>Specter Viewer</strong></a> - 
A PySide6-based GUI application for visual inspection, object hierarchy browsing, property editing, method invocation, and test authoring. Acts as the visual control center for live applications.

- <a href="/specter_debugger/README.md"><strong>Specter Debugger</strong></a> - 
A command-line-oriented module used to run scripted automation scenarios against Specter targets. Useful for continuous integration, regression testing, and interactive debugging.

Together, these modules enable:
- Injection of the Specter DLL into live or launchable Qt processes
- Tree-based exploration of the QObject hierarchy
- Real-time editing of properties and invocation of slots/methods
- Recording and playback of user interactions for test automation
- Streamlined debugging and scripting workflows for developers and QA

Whether you're testing, inspecting, or integrating with complex Qt systems, the Specter suite provides a powerful and flexible interface for runtime control and automation.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- BUILT WITH -->
## Built With

* [![Python][Python]][Python-url]
* [![Poetry][Poetry]][Poetry-url]
* [![PySide6][PySide6]][PySide6-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

This guide explains how to set up and deploy the specter_client project locally using Poetry and pyside6-deploy.

### Prerequisites

Make sure you have the following installed:
- Python 3.12
- Poetry (With Monorepo Plugin)

To install Poetry and add require plugin:
```sh
pip install poetry
poetry self add poetry-monorepo-dependency-plugin
```

### Installation
Clone the repository and install dependencies using Poetry:
```sh
git clone https://github.com/AdamMinge/specter_client.git
cd specter_client
poetry install
```

### Build Modules
Compile all necessary resources for each module, including:
- Generating Python bindings from .proto files (gRPC)
- Compiling Qt resource files (.qrc)
```sh
poetry run build
```
_Use this command to generate all the code and assets needed for the modules to function properly._

### Deploy Modules
Package and deploy each module into distributable executables.
```sh
poetry run deploy
```
_This command creates deployment configs and builds the final executables for your modules, ready for distribution or testing._

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Top contributors:

<a href="https://github.com/AdamMinge/specter_client/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=AdamMinge/specter_client" alt="contrib.rocks image" />
</a>

<!-- LICENSE -->
## License

Distributed under the Unlicense License. See `LICENSE.txt` for more information.

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