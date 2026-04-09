"""AURa setup — pip installable package."""

from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="aura-ai-os",
    version="1.2.0",
    author="AURa Project",
    description="Autonomous Universal Resource Architecture — AI Virtual System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Cbetts1/Damn-it-xm",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.9",
    install_requires=[
        # Core (no heavy deps — works out of the box)
    ],
    extras_require={
        "transformers": [
            "transformers>=4.36.0",
            "torch>=2.0.0",
        ],
        "api": [
            "httpx>=0.25.0",
        ],
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "aura=aura.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: System :: Operating System",
    ],
    keywords="ai os virtual cloud cpu server llm open-source",
)
