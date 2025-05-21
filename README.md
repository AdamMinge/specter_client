<a id="readme-top"></a>

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![project_license][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/AdamMinge/specterUI">
    <img src="images/logo.png" alt="Logo" width="80" height="80">
  </a>

<h3 align="center">SpecterUI</h3>

  <p align="center">
    SpecterUI is a PySide6-based frontend that connects to the Specter-injected target application, offering a rich interface for navigating, controlling, and automating its internals. It simplifies interaction with the gRPC backend through visual object exploration and real-time editing tools.
    <br />
    <a href="https://github.com/AdamMinge/specterUI"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/AdamMinge/specterUI">View Demo</a>
    &middot;
    <a href="https://github.com/AdamMinge/specterUI/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    &middot;
    <a href="https://github.com/AdamMinge/specterUI/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
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
        <li><a href="#initial-deployment-setup">Initial Deployment Setup</a></li>
        <li><a href="#build-the-rcc">Build the RCC</a></li>
        <li><a href="#build-the-app">Build the App</a></li>
      </ul>
    </li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About The Project

SpecterUI serves as the visual cockpit for working with applications instrumented by the Specter DLL. Built with PySide6 for a responsive and extensible UI, it provides users with a streamlined way to interface with live application data exposed via gRPC.

SpecterUI enables:

- Injection of Specter into new or existing Qt processes
- Tree-based browsing of the application’s QObject hierarchy
- Real-time inspection and editing of object properties
- Method and slot invocation through an interactive UI
- Action recording for repeatable automation tasks

Designed for developers, QA engineers, and tool integrators, SpecterUI abstracts the lower-level gRPC interface into an accessible and powerful control panel, enabling efficient inspection, debugging, and scripting of Qt applications at runtime.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- BUILT WITH -->
## Built With

* [![Python][Python]][Python-url]
* [![Poetry][Poetry]][Poetry-url]
* [![PySide6][PySide6]][PySide6-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

This guide explains how to set up and deploy the specterUI project locally using Poetry and pyside6-deploy.

### Prerequisites

Make sure you have the following installed:
- Python 3.12
- Poetry

To install Poetry:
```sh
pip install poetry
```

### Installation
Clone the repository and install dependencies using Poetry:
```sh
git clone https://github.com/AdamMinge/specterUI.git
cd specterUI
poetry install
```

### Initial Deployment Setup

##### 1.Generate the initial PySide6 deployment config:
```sh
poetry run pyside6-deploy --init specter/__main__.py
```

##### 2.Edit the generated pyside6deploy.spec:
Update the following fields:
```sh
[app]
title = specterUI
exec_directory = build/bin
icon = images/logo.png
```
You may use an absolute or relative path for exec_directory and icon. Ensure input_file points to specter/main.py.

##### 3. Move the spec file to the root (optional but recommended):
```sh
mv specter/pyside6deploy.spec .
```

### Build the RCC
Run the rcc building using specterui.qrc
```sh
poetry run pyside6-rcc -o specterui/resources/rcc.py specterui/resources/specterui.qrc
```

### Build the GRPC
Run the grpc/proto building using specter.proto
```sh
python -m grpc_tools.protoc -I. --python_out=. specterui/proto/specter.proto --grpc_python_out=.
```

### Build the App
Run the deployment using your updated spec file:
```sh
poetry run pyside6-deploy -c pyside6deploy.spec
```
The compiled executable will be located in the directory you set under exec_directory (e.g. build/bin/).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ROADMAP -->
## Roadmap

- [ ] Objects Dock
  - [ ] Display object hierarchy
- [ ] Properties Dock
  - [ ] Display selected object properties
  - [ ] Add / Remove / Edit object properties
- [ ] Methods Dock
  - [ ] Display available methods of selected object
  - [ ] Call selected method with parameters
- [ ] Terminal Dock
  - [ ] Execute gRPC commands manually
- [ ] Recorder Dock
  - [ ] Enable/Disable recording of actions
  - [ ] Show list of recorded actions


See the [open issues](https://github.com/AdamMinge/specterUI/issues) for a full list of proposed features (and known issues).

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

<a href="https://github.com/AdamMinge/specterUI/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=AdamMinge/specterUI" alt="contrib.rocks image" />
</a>

<!-- LICENSE -->
## License

Distributed under the Unlicense License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- CONTACT -->
## Contact

Adam Minge - minge.adam@gmail.com

Project Link: [https://github.com/AdamMinge/specterUI](https://github.com/AdamMinge/specterUI)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/AdamMinge/specterUI.svg?style=for-the-badge
[contributors-url]: https://github.com/AdamMinge/specterUI/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/AdamMinge/specterUI.svg?style=for-the-badge
[forks-url]: https://github.com/AdamMinge/specterUI/network/members
[stars-shield]: https://img.shields.io/github/stars/AdamMinge/specterUI.svg?style=for-the-badge
[stars-url]: https://github.com/AdamMinge/specterUI/stargazers
[issues-shield]: https://img.shields.io/github/issues/AdamMinge/specterUI.svg?style=for-the-badge
[issues-url]: https://github.com/AdamMinge/specterUI/issues
[license-shield]: https://img.shields.io/github/license/AdamMinge/specterUI.svg?style=for-the-badge
[license-url]: https://github.com/AdamMinge/specterUI/blob/master/LICENSE.txt
[Python]: https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white
[Python-url]: https://www.python.org/
[Poetry]: https://img.shields.io/badge/Poetry-1.8+-blueviolet?logo=python&logoColor=white
[Poetry-url]: https://python-poetry.org/
[PySide6]: https://img.shields.io/badge/PySide6-6.9+-green?logo=qt&logoColor=white
[PySide6-url]: https://doc.qt.io/qtforpython-6/index.html