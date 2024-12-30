from setuptools import setup, find_packages

setup(
    name="leaky-bucket-py",
    version="0.1.1",
    description="Leaky bucket implementation in Python with different persistence options",
    author="DuneRaccoon",
    author_email="benjamincsherro@hotmail.com",
    license="MIT",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    keywords=["rate-limiter", "asyncio", "leaky-bucket", "redis", "sqlite3"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11"
    ],
    packages=find_packages(exclude=["tests*", "docs*", "examples*"]),
    install_requires=[
        "redis>=3.5.3",
        "pytest>=6.2.4",
    ],
    python_requires=">=3.7",
)
