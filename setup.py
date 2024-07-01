from setuptools import setup

def readme():
    with open('README.md') as f:
        return f.read()

setup(name='aneupy',
      version='0.1',
      packages=['aneupy'],
      description='Python code for simulating Abdominal Aorta Aneurysms in Abaqus/CAE',
      long_description=readme(),
      url='https://github.com/UDC-GME/aneupy',
      author='Jacobo Diaz',
      author_email='jdiaz@udc.es',
      classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Education',
        'Topic :: Scientific/Engineering',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
      ],
      license='GPL',
      install_requires=[
                'sympy',
                'numpy',
                ],
      include_package_data=True,
      zip_safe=False)
