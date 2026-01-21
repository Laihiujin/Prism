from setuptools import find_packages, setup


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="openmanus",
    version="0.1.0",
    author="mannaandpoem and OpenManus Team",
    author_email="mannaandpoem@gmail.com",
    description="A versatile agent that can solve various tasks using multiple tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/FoundationAgents/OpenManus",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.10.4,<3.0.0",
        "openai>=1.58.1,<1.70.0",
        "tenacity~=9.0.0",
        "pyyaml~=6.0.2",
        "loguru~=0.7.3",
        "structlog~=24.4.0",
        "numpy>=1.26.0",
        "html2text~=2024.2.26",
        "gymnasium>=1.0,<1.2",
        "pillow>=10.4,<11.2",
        "browsergym~=0.13.3",
        "uvicorn>=0.34.0,<0.35.0",
        "unidiff~=0.7.5",
        "browser-use>=0.1.40,<0.2.0",
        "googlesearch-python~=1.3.0",
        "baidusearch>=0.1.0",
        "duckduckgo_search>=6.0.0",
        "aiofiles>=24.1.0",
        "pydantic_core>=2.27.2,<2.30.0",
        "colorama~=0.4.6",
        "playwright>=1.48.0",
        "httpx>=0.27.0",
        "mcp>=1.0.0",
        "boto3>=1.35.0",
        "requests>=2.32.0",
        "beautifulsoup4>=4.12.0",
        "crawl4ai>=0.6.0",
        "docker>=7.0.0",
        "tiktoken>=0.8.0",
        "tomli>=2.0.0",
        "daytona-sdk>=0.1.0",
    ],
    extras_require={
        "local-llm": [
            "datasets>=3.2,<3.6",
            # "huggingface-hub>=0.25.0",
            "litellm>=1.48.0",
            # "torch>=2.0.0",
            # "transformers>=4.40.0",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "openmanus=main:main",
        ],
    },
)
