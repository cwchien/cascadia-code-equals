# Cascadia Code fork with a joined equals ligature

This is a fork of Cascadia Code, with the joined `==` ligature added back.

## Images (taken from Kate)

Current Cascadia Code:  
![Without the joined ligature](./images/equal_equal_regular_cascadia.png)  

This fork of Cascadia Code:  
![With the joined ligature](./images/equal_equal_added_back.png)

## Build Requirements

- Python 3.14
- [uv](https://docs.astral.sh/uv/)

### How to build

Create a virtual environment, install requirements, and run the build script.

```sh
uv venv --python 3.14
uv pip install -r requirements.txt
uv run build.py
```

The build only produces the static TTFs of Cascadia Code Regular, Bold, Italic and Bold Italic:

- `build/ttf/unhinted/`: without hinting
- `build/ttf/hinted/`: hinted with ttfautohint
