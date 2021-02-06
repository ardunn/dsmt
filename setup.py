import os
from setuptools import setup, find_packages


version = "0.0.1.2021.02.05"
module_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(module_dir, "requirements.txt"), "r") as f:
    requirements = f.read().replace(" ", "").split("\n")

long_description = \
    """
    dsmt (dumb simple monitor tool): an ultra-minimal and flexible server monitoring tool
    """

setup(
    name='dsmt',
    version=str(version),
    description='An ultra-minimal and flexible server monitoring tool',
    url='https://github.com/ardunn/dsmt',
    author='Alex Dunn',
    author_email='denhaus@gmail.com',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='modified BSD',
    classifiers=[
        'Development Status :: 3 - Alpha',
    ],
    keywords='productivity',
    test_suite='dsmt',
    tests_require='tests',
    packages=find_packages(),
    # package_data={'dsmt': ['defaults.yaml']},
    install_requires=requirements,
    data_files=['README.md', 'LICENSE'],
    include_package_data=True
)