# Typer

<p align="center">
<a href="https://typer.tiangolo.com"><img src="https://typer.tiangolo.com/img/logo-margin/logo-margin-vector.svg#only-light" alt="Typer"></a>
</p>

<p align="center">
    <em>Typer, build great CLIs. Easy to code. Based on Python type hints.</em>
</p>

<p align="center">
<a href="https://github.com/fastapi/typer/actions?query=workflow%3ATest+event%3Apush+branch%3Amaster">
    <img src="https://github.com/fastapi/typer/actions/workflows/test.yml/badge.svg?event=push&branch=master" alt="Test">
</a>
<a href="https://github.com/fastapi/typer/actions?query=workflow%3APublish">
    <img src="https://github.com/fastapi/typer/workflows/Publish/badge.svg" alt="Publish">
</a>
<a href="https://coverage-badge.samuelcolvin.workers.dev/redirect/fastapi/typer">
    <img src="https://coverage-badge.samuelcolvin.workers.dev/fastapi/typer.svg" alt="Coverage">
<a href="https://pypi.org/project/typer">
    <img src="https://img.shields.io/pip/v/typer?color=%2334D058&label=pypi%20package" alt="Package version">
</a>
</p>

---

## Description
Typer is a library for building command-line interface (CLI) applications that users will **love using** and developers will **love creating**. It leverages modern Python features such as type hints, providing an intuitive experience for both developers and users.

## Quick Start
1. **Installation**:
   ```bash
   pip install typer
   ```
2. **Creating a Simple Command**:
   ```python
   import typer
   
   app = typer.Typer()
   
   @app.command()
   def hello(name: str):
       typer.echo(f"Hello {name}")
   
   if __name__ == "__main__":
       app()
   ```
   Run the command:
   ```bash
   python your_script.py hello World
   ```

## Architecture Overview
- **Main Components**:
  - `typer/main.py`: Handles command registration and invocation.
  - `typer/params.py`: Manages parameter captures and type validation.
  - `typer/core.py`: Contains core functionalities and logic.
- **Flow**:
  1. User invokes the CLI.
  2. Commands are registered and parsed.
  3. Parameters validated.
  4. Commands executed.

## Configuration
Using environment variables or a configuration file is recommended for customizing application behavior.

## Contributing
Interested in contributing? We welcome community contributions! Please refer to our [contributing guidelines](https://github.com/fastapi/typer/blob/master/CONTRIBUTING.md).

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.