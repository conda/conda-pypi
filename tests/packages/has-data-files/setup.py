from setuptools import find_packages, setup

setup(
    name="test-package-with-data",
    version="1.0.0",
    packages=find_packages(),
    data_files=[
        ("share/test-package-with-data/data", ["test_package_with_data/data/test.txt"]),
        ("share/test-package-with-data", ["test_package_with_data/share/config.json"]),
    ],
)
