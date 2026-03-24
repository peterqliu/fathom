# Setting up pip on macOS

## Check if pip is already installed

First, check if pip is already installed:

```bash
pip --version
```

or

```bash
pip3 --version
```

## Install pip using the recommended method:

1. Download the get-pip.py script:

```bash
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
```

2. Run the script:

```bash
python get-pip.py
```

or using Python 3 (recommended):

```bash
python3 get-pip.py
```

3. Verify installation:

```bash
pip --version
```

or

```bash
pip3 --version
```

## Alternative: Install pip with Homebrew

If you have Homebrew installed:

```bash
brew install python
```

This installs Python 3 with pip3 included.

## After pip is installed

Now you can install the required packages for this project:

```bash
pip install -r requirements.txt
```

or

```bash
pip3 install -r requirements.txt
``` 