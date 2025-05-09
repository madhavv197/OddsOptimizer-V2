from setuptools import setup, find_packages

setup(
    name="OddsOptimizer",
    version="0.2",
    packages=find_packages(),  # auto-detects /utils, /engine, etc.
    include_package_data=True,
)