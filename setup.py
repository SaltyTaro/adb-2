from setuptools import setup, find_packages

# Read requirements
with open('backend/requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="dependency-intelligence",
    version="1.0.0",
    description="Advanced Dependency Intelligence Platform",
    author="Your Organization",
    author_email="contact@example.com",
    url="https://github.com/yourusername/advanced-dependency-intelligence",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'deptool=cli.main:main',
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Version Control",
    ],
    python_requires=">=3.8",
)