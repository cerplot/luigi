General Architecture
====================
The core of the system will be implemented in c++ for scalability and speed.
However, we will use python for the high-level logic and for the command 
line interface. We will discuss that logic in a later stages. Let's first 
talk about the c++ core which needs to be implemented first.

C++ core is divided into several steps, each of which reads data from the 
previous step, processes it and provides it to the next step in a pipeline 
fashion:

Step1 -> (save output) -> Step2 -> (save output) ->Step3 -> ... -> StepN
               |                        |                      |
               v                        v                      v

As you can see, C++ optionally saves intermediate data after each step,
 and the next layer can read that data and do its work just by using that data.
(i.e. no need to run previous step provided data was saved after it.)
Researcher should be able to use python to read/modify/write that saved c++ data as well.
This will be important for researching different ideas in the future.

Question arises how to save data so that the process is fast, efficient and
easily readable by python? Let's for now use binary format to write/read data by
C++ code and numpy. Later we might change it to some other format if we find
out that there are better ways.

Demo 1: Saving data in binary format::

    #include <fstream>
    #include <vector>

    int main() {
        std::vector<float> vec = {1, 2, 3, 4, 5};

        std::ofstream out_file("arr1.bin", std::ios::binary);
        if (out_file.is_open()) {
            out_file.write(reinterpret_cast<const char*>(&vec[0]), vec.size() * sizeof(float));
            out_file.close();
        }

        return 0;
    }

This code creates a binary file named arr1.bin and writes the contents of the vector vec to it.
To read this binary file as a numpy array in Python, you can use the numpy.fromfile function::

    import numpy as np
    arr = np.fromfile('arr1.bin', dtype=np.float32)
    print(arr)


To write a numpy array to a binary file in Python, you can use the numpy.ndarray.tofile function. Here's an example::

    import numpy as np
    arr = np.array([1, 2, 3, 4, 5], dtype=np.float32)
    arr.tofile('arr1.bin')



This code creates a binary file named arr1.bin and writes the contents of the numpy array arr to it.  To read this binary file in C++, you can use the std::ifstream class from the <fstream> library. Here's how you can do it::

        #include <fstream>
        #include <vector>

        int main() {
            std::vector<float> vec(5);

            std::ifstream in_file("arr1.bin", std::ios::binary);
            if (in_file.is_open()) {
                in_file.read(reinterpret_cast<char*>(&vec[0]), vec.size() * sizeof(float));
                in_file.close();
            }

            for (auto v : vec) {
                std::cout << v << std::endl;
            }

            return 0;
        }

If you prefer more flexibility, you can look at implementation of very small use the cnpy library:
https://github.com/rogersce/cnpy/blob/master/cnpy.cpp

Here how to write c++ vector into a file using that code:

    #include <cnpy.h>
    #include <vector>
    #include <iostream>

    int main()
    {
        std::vector<float> vec = {1, 2, 3, 4, 5};
        cnpy::npy_save("arr1.npy", &vec[0], {5}, "w");
        return 0;
    }

Here is how to read it in python:

    import numpy as np
    arr = np.load('arr1.npy')
    print(arr)


If you prefer using a library that is more widely used, you can use the HDF5 format.
But I am not sure if it is worth the effort to use it for our purposes.

So research will be done in python, and then best ideas will be implemented in C++.
This is an optimal combination of performance and flexibility. It should not be required to
know C++ to do research, but it is required to know C++ to implement the best ideas
in the production code. This is a good separation of concerns.


Configuration
=============
There is no need to create our own configuration file format. For configuration,
we will use toml file. https://toml.io/en/ This is a simple format that python
can read natively and C++ has a good library for it as well.
(e.g. https://marzer.github.io/tomlplusplus/).  We will talk about the content
of the configuration file later. For now let's just say that it will contain the
paths to the data, the list of stocks, the list of indicators, and some other
parameters that we will need in the future.


Build System
============
The build system will be CMake which is standard nowadays. And if in the future you want
to compile the code on windows, it will be easy to make that transition. And
possibly some might want to use Windows for development, and CMake will make that transition smooth
as well.


Binding C++ to Python
=====================
We will need python access to the C++ internals (calling C++ functions from python, for example).
There are many ways of doing it and for our purposes pybind11 - can be used
(open for other suggestions, but it seems like the best choice these days).


MKL
===
MLK (https://www.intel.com/content/www/us/en/developer/tools/oneapi/onemkl.html) will be used at some point.
We should be able to compile it. It is a standard library for numerical computations and it is used by many other libraries as well. For now this is the only numerical library we will use, but we might add others in the future.


sqlite
=======
Another library we will need is sqlite. Stats and other outputs will be saved in a sqlite database.
Again very standard and easy to use.


Unit tests are done with google test (C++) (if there is no objection) and pytest (python).
compiler is gcc (open for other suggestions, but it seems to be the standard choice).
Anyways, multiple compilers can be used, but we will use gcc for now. Switching to another compiler
should be easy and usefully exercise for the future.
clang-format is used for code formatting.

GIT
===
Version control is git. Later we can decide to choose another branching strategy.
But, for now, we will keep things simple:
- master branch is always stable and can be deployed to production.
- development branch is used for development.
- feature branches are used for developing new features. and are merged into the development branch when the feature is ready.

It would be nice to have a CI/CD pipeline, using jenkins.

Later we will add other information, but for now this is enough to setup the development environment.


Data Layer
===========
Everything starts with raw tick data.
Depending on provider, the data can be in different formats.
The role of the data layer is to provide a unified interface to access the data, so we should not worry about those differences.
It should be able to read data from different sources, convert it to unified format and provide it to the upper layers.

Data layer reads data (using different processes depending on the source), and returns it in a units that we will call tick.


Pseudocode
-----------
The Data Layer should have a method to get the next tick:

    DataSource * source = get_data_source(PATH_TO_DATA_SOURCE);

    Tick tick1 = source->next();
    Tick tick2 = source->next();

`Tick` object has some attributes like:
    - type (can be 'BT' to indicate it has new bid and trade information, etc.)
    - timestamp (in microseconds?)
    - bidSize
    - bidPrice
    - askSize
    - askPrice
    - tradeSize
    - tradePrice
    - fingerprint (unique identifier for the tick. We should decide how to generate this unique identifier. It can be a hash of the tick data, for example.)
- etc.


if (tick.type == BT){
    uint tradeSize = tick.tradeSize;
    float tradePrice = tick.tradePrice;
}

We need to have a method to get the next tick only for a given stock as well:

    DataSource *source = get_stock_data_source(stock_id, PATH_TO_DATA_SOURCE)


That pretty much covers the data layer. It hides the complexity of the data source and provides a simple interface to access the data tick by tick.
Data is accessed in a sequential manner using `next` method.

NOTE: Later, we need to have python interface to the data layer as well so this function can be imported and called from python.
    But for now let's focus on the C++ implementation.

Once the data layer is implemented, we can start implementing the next layer, which is the Indicator Layer.


Indicator Layer
===============
In this layer, we will calculate the indicators that we will use in our strategies.
Along with indicators, we will also calculate some other parameters that we will use in the future
(e.g. some stock-specific averages).

Indicators can be calculated in parallel for every stock.
Thus, we can save data in a format that is easy to read stock by stock, and then calculate the indicators in parallel.
(That is why we described the `get_stock_data_source` method in the data layer.)
Parallel calculation should be done since we are talking about 1000's of stocks, for 100's of days and each stock has
1000's of indicators and parameters.

for ticker in stocks:
    source = data_layer.get_stock_data(ticker)
    for indicator_name in indicators:
        indicator[stock][indicator_name] = calculate_indicator(ticker, indicator_name)


def calculate_indicator(source, indicator_name):
    while True:
        tick = source.get_next_tick()
        ...
        # do calculations
        ...
        par1 = calculate_parameter1(tick)


Example::

    from numpy import exp
    import numpy as np


    class Indicator:
        def __init__(self, source):
            self.source = source
            self.ticker = source.ticker
            self.stock_model = None

            self.LT_cont = 8

            self.taus = [
                0.0,
                exp(-1.0 / 1),
                exp(-1.0 / 3),
                exp(-1.0 / 9),
                exp(-1.0 / 27),
                exp(-1.0 / 81),
                exp(-1.0 / 243),
                exp(-1.0 / 729),
            ]

            self.Ninds = 10
            self.Ntaus = len(self.taus)

            self.Nbasis = self.Ninds * self.Ntaus

            self.Z = np.tile(self.taus, self.Ninds)
            self.U = np.zeros(self.Ninds)
            self.X = np.zeros(self.Nbasis)

            self.X_old = np.zeros(self.Nbasis)

            self.askPrice = 0.0
            self.bidPrice = 0.0
            self.askSize = 0.0
            self.bidSize = 0.0
            self.tradeSize = 0.0
            self.price = 0.0

            self.quote = 0.0
            self.virtualTradeCount = 0.0
            self.tradeSide = 0.0
            self.iSize = 0.0

            self.lastQuote = None
            self.lastPrice = None
            self.lastQuoteSize = 0.0
            self.lastQuoteLTSize = 0.0

            self.isValidQuote = False
            self.isValidSize = False
            self.hasTrade = False

        def next_value(self):
            tick = self.source.get_next_tick()
            time_stamp = tick.timestamp
            bat  = tick.type
            val = tick.value

            if 'BID' == bat:
                if self.bidPrice > 0:
                    if val > self.bidPrice:
                        self.virtualTradeCount += 1
                    elif val < self.bidPrice:
                        self.virtualTradeCount -= 1
                # first time init
                self.bidPrice = val

                self.isValidQuote = self.askPrice > self.bidPrice > 0

                if self.isValidQuote:
                    self.quote = 0.5 * (self.askPrice + self.bidPrice)

            elif 'BID_SIZE' == bat:
                if self.bidSize > 0:
                    if val > self.bidSize:
                        self.virtualTradeCount += 1
                    elif val < self.bidSize:
                        self.virtualTradeCount -= 1
                self.bidSize = val
                self.isValidSize = self.bidSize > 0 and self.askSize > 0

            elif 'ASK' == bat:
                if self.askPrice > 0:
                    if val > self.askPrice:
                        self.virtualTradeCount += 1
                    elif val < self.askPrice:
                        self.virtualTradeCount -= 1

                self.askPrice = val

                self.isValidQuote = self.askPrice > self.bidPrice > 0
                if self.isValidQuote:
                    self.quote = 0.5 * (self.askPrice + self.bidPrice)

            elif 'ASK_SIZE' == bat:
                if self.askSize > 0:
                    if val > self.askSize:
                        self.virtualTradeCount -= 1
                    elif val < self.askSize:
                        self.virtualTradeCount += 1
                self.askSize = val
                self.isValidSize = self.bidSize > 0 and self.askSize > 0

            elif 'LAST' == bat:
                if self.price > 0:
                    self.lastPrice = self.price
                else:
                    self.lastPrice = val

                self.price = val
                self.hasTrade = True
                if self.isValidQuote and self.askPrice > self.bidPrice:
                    self.tradeSide = 1 if self.price > self.quote else -1

            elif 'LAST_SIZE' == bat:
                self.tradeSize = val
                self.iSize = val * self.tradeSide

            if self.isValidQuote and self.isValidSize and self.hasTrade:

                skew = (self.bidSize - self.askSize) / (self.bidSize + self.askSize)
                self.quoteSize = np.arctan(skew)
                self.quoteLTSize = np.arctan(self.LT_cont * skew)

                self.iprice = self.price - self.quote

                if self.lastQuote is None:
                    self.lastQuote = self.quote

                self.U[0] = self.price - self.lastPrice
                self.U[1] = self.quote - self.lastQuote
                self.U[2] = self.iprice
                self.U[3] = self.tradeSide
                self.U[4] = self.quoteSize - self.lastQuoteSize
                self.U[5] = self.quoteSize
                self.U[6] = self.quoteLTSize - self.lastQuoteLTSize
                self.U[7] = self.quoteLTSize
                self.U[8] = self.virtualTradeCount
                self.U[9] = self.iSize

                # append indicators to predictor model state
                self.X += (1 - self.Z) * np.repeat(self.U, self.Ntaus)

                if self.output and self.close_time > time_stamp > self.open_time:
                    row = '{}\t{}\t{}\t'.format(time_stamp, self.bidPrice, self.askPrice)
                    for x in self.X:
                        row += "{}\t".format(x)
                    self.X_file.write(row + '\n')
                    self.X_file.flush()

                # advance the state
                self.X *= self.Z

                self.lastQuote = self.quote
                self.lastQuoteSize = self.quoteSize
                self.lastQuoteLTSize = self.quoteLTSize

                self.virtualTradeCount = 0.0
                self.hasTrade = False



Parallelism
===========
We need to know how to do parallelism in C++. We need to be able to calculate indicators in parallel for every stock.
How to accomplish it depends on what is available and what is architecture of the system. So please learn about it and try to implement.




Trun is a Python (3.10, 3.11 3.12) package that helps you build complex
pipelines of batch jobs. It handles dependency resolution, workflow management,
visualization, handling failures, command line integration, and much more.

Getting Started
---------------

Run ``pip install trun`` to install the latest stable version from `PyPI
<https://pypi.python.org/pypi/trun>`_. `Documentation for the latest release
<https://trun.readthedocs.io/en/stable/>`__ is hosted on readthedocs.

Run ``pip install trun[toml]`` to install Trun with `TOML-based configs
<https://trun.readthedocs.io/en/stable/configuration.html>`__ support.

For the bleeding edge code, ``pip install
git+https://github.com/spotify/trun.git``. `Bleeding edge documentation
<https://trun.readthedocs.io/en/latest/>`__ is also available.

Background
----------

The purpose of Trun is to address all the plumbing typically associated
with long-running batch processes. You want to chain many steps,
automate them, and failures *will* happen. These steps can be anything,
but are typically long running things like
`Hadoop <http://hadoop.apache.org/>`_ jobs, dumping data to/from
databases, running machine learning algorithms, or anything else.

There are other software packages that focus on lower level aspects of
data processing, like `Hive <http://hive.apache.org/>`__,
`Pig <http://pig.apache.org/>`_, or
`Cascading <http://www.cascading.org/>`_. Trun is not a framework to
replace these. Instead it helps you stitch many steps together, where
each step can be a `Hive query <https://trun.readthedocs.io/en/latest/api/trun.contrib.hive.html>`__,
a `Hadoop job in Java <https://trun.readthedocs.io/en/latest/api/trun.contrib.hadoop_jar.html>`_,
a  `Spark job in Scala or Python <https://trun.readthedocs.io/en/latest/api/trun.contrib.spark.html>`_,
a Python snippet,
`dumping a table <https://trun.readthedocs.io/en/latest/api/trun.contrib.sqla.html>`_
from a database, or anything else. It's easy to build up
long-running pipelines that comprise thousands of steps and take days or
weeks to complete. Trun takes care of a lot of the workflow management
so that you can focus on the steps themselves and their dependencies.

You can build pretty much any step you want, but Trun also comes with a
*toolbox* of several common step templates that you use. It includes
support for running
`Python mapreduce jobs <https://trun.readthedocs.io/en/latest/api/trun.contrib.hadoop.html>`_
in Hadoop, as well as
`Hive <https://trun.readthedocs.io/en/latest/api/trun.contrib.hive.html>`__,
and `Pig <https://trun.readthedocs.io/en/latest/api/trun.contrib.pig.html>`__,
jobs. It also comes with
`file system abstractions for HDFS <https://trun.readthedocs.io/en/latest/api/trun.contrib.hdfs.html>`_,
and local files that ensures all file system operations are atomic. This
is important because it means your data pipeline will not crash in a
state containing partial data.

Visualiser page
---------------

The Trun server comes with a web interface too, so you can search and filter
among all your steps.

.. figure:: https://raw.githubusercontent.com/spotify/trun/master/doc/visualiser_front_page.png
   :alt: Visualiser page

Dependency graph example
------------------------

Just to give you an idea of what Trun does, this is a screen shot from
something we are running in production. Using Trun's visualiser, we get
a nice visual overview of the dependency graph of the workflow. Each
node represents a step which has to be run. Green steps are already
completed whereas yellow steps are yet to be run. Most of these steps
are C++ jobs, but there are also some things that implemented in python
and build up data files.


Philosophy
----------

where you have certain steps and these steps in turn may have dependencies on other steps.

Everything in Trun is in Python. Instead of XML configuration or
similar external data files, the dependency graph is specified *within
Python*. This makes it easy to build up complex dependency graphs of
steps, where the dependencies can involve date algebra or recursive
references to other versions of the same step.



Currently, Trun is not released on any particular schedule and it is not
strictly abiding semantic versioning. Whenever possible, bump major version when you make incompatible API changes, minor version when you add functionality in a backwards compatible manner, and patch version when you make backwards compatible bug fixes.



# how
==========
To read binary data saved from a C++ program in Python, you can use the struct module which provides pack and unpack functions for working with variable-length binary record formats. The struct module performs conversions between Python values and C structs represented as Python bytes objects.  Here is a basic example::

    import struct
    
    # Open the file in binary mode
    with open('binary_file.bin', 'rb') as f:
        data = f.read()
    
    # Unpack the data
    # Here 'i' is for int, 'f' is for float. The number of these depends on how your data is structured.
    # This is just an example, you need to replace it with your actual format.
    unpacked_data = struct.unpack('if', data)
    
    print(unpacked_data)


In the above code, replace 'if' with the actual format of your data. The format codes like 'i' for an integer and 'f' for a float, correspond to the types of data that you're reading. The number of these format codes should match the number of data elements for each record in the binary file.  Please note that this is a very basic example. The actual implementation may vary depending on how the binary data is structured in your file. You need to know the exact structure (data types, order, etc.) of the binary data to correctly unpack it in Python.


To ensure compatibility between C++ and Python when dealing with binary data, you should use a common data format. One such format is the binary format used by the struct module in Python, which corresponds to the format used by the fwrite and fread functions in C++.  Here's a step-by-step plan:  
* In C++, use fwrite to write binary data to a file. You need to specify the data you want to write and the size of the data type.  
* In Python, use the struct module to read the binary data from the file. You need to specify the format of the data in the file, which should match the data type used in C++.  
Here's how you can do it:  C++ code for writing binary data::

    #include <iostream>
    #include <fstream>
    
    int main() {
        std::ofstream outfile ("test.bin", std::ofstream::binary);
    
        // write integer
        int a = 123;
        outfile.write(reinterpret_cast<char*>(&a), sizeof(int));
    
        // write float
        float b = 456.789f;
        outfile.write(reinterpret_cast<char*>(&b), sizeof(float));
    
        outfile.close();
    
        return 0;
    }


Python code for reading the binary data::

    import struct
    
    # Open the file in binary mode
    with open('test.bin', 'rb') as f:
        data = f.read()
    
    # Unpack the data
    # 'i' is for int, 'f' is for float
    unpacked_data = struct.unpack('if', data)
    
    print(unpacked_data)



In the Python code, 'if' is the format string for struct.unpack(). 'i' stands for integer and 'f' stands for float, which matches the types of data written in the C++ code.  Please note that this is a very basic example. The actual implementation may vary depending on how the binary data is structured in your file. You need to know the exact structure (data types, order, etc.) of the binary data to correctly unpack it in Python.


To read and write large vectors from C++, you can use the std::vector data type in combination with file streams. Here's a simple example of how you can do this:  C++ code for writing a large vector to a binary file::

    #include <iostream>
    #include <fstream>
    #include <vector>
    
    int main() {
        std::ofstream outfile ("test.bin", std::ofstream::binary);
    
        // Create a large vector
        std::vector<int> vec(1000000);
        for(int i = 0; i < 1000000; ++i) {
            vec[i] = i;
        }
    
        // Write the entire vector to the file
        outfile.write(reinterpret_cast<const char*>(&vec[0]), vec.size()*sizeof(int));
    
        outfile.close();
    
        return 0;
    }

C++ code for reading a large vector from a binary file::
    
        #include <iostream>
        #include <fstream>
        #include <vector>
        
        int main() {
            std::ifstream infile ("test.bin", std::ifstream::binary);
        
            // Read the entire file into a vector
            infile.seekg(0, infile.end);
            int length = infile.tellg();
            infile.seekg(0, infile.beg);
        
            std::vector<int> vec(length/sizeof(int));
            infile.read(reinterpret_cast<char*>(&vec[0]), length);
        
            infile.close();
        
            // Print the first 10 elements of the vector
            for(int i = 0; i < 10; ++i) {
                std::cout << vec[i] << std::endl;
            }
        
            return 0;
        }


In the Python side, you can use the struct module to read the binary data from the file. Here's how you can do it:  Python cod

    import struct
    
    # Open the file in binary mode
    with open('test.bin', 'rb') as f:
        data = f.read()
    
    # Calculate the number of integers in the data
    num_elements = len(data) // struct.calcsize('i')
    
    # Unpack the data
    unpacked_data = struct.unpack('{}i'.format(num_elements), data)
    
    print(unpacked_data)


In the Python code, 'i' is the format string for struct.unpack(), which stands for integer, matching the type of data written in the C++ code.



You can use Python's buffer protocol to handle binary data. The buffer protocol provides a way to access the internal data of an object. This allows different objects to share their data, and it's a way to pass data between C and Python.  Here's an example of how you can use the buffer protocol with the memoryview function in Python to read binary data::

    # Open the file in binary mode
    with open('test.bin', 'rb') as f:
        data = f.read()
    
    # Create a memoryview of the data
    buffer = memoryview(data)
    
    # Unpack the data
    # 'i' is for int, 'f' is for float
    unpacked_data = struct.unpack('if', buffer)
    
    print(unpacked_data)



In this example, memoryview(data) creates a memory view object of the binary data. This object can then be used with the struct.unpack() function to unpack the binary data.  Please note that the buffer protocol is a lower-level interface and may not be as straightforward to use as the struct module for handling binary data. It's typically used in performance-critical or low-level code.

To read C++ binary files into numpy arrays as fast as possible, you can use the `numpy.fromfile()` function. This function is designed to create a numpy array from a binary file in a very efficient manner.

Here is a simple example:

```python
import numpy as np

# Open the file in binary mode
with open('test.bin', 'rb') as f:
    # Read the entire file into a numpy array
    array = np.fromfile(f, dtype=np.int32)  # dtype should match the type of data written in the C++ code

print(array)
```

In this example, `'test.bin'` is the name of the binary file you want to read, and `np.int32` is the data type of the elements in the array. You should replace these with the actual file name and data type according to your specific situation.

Please note that the `dtype` argument should match the type of data written in the C++ code. For example, if you wrote `float` data in the C++ code, you should use `np.float32` or `np.float64` depending on the precision. If you wrote `int` data, you should use `np.int32` or `np.int64` depending on the size of the integers.


To write numpy arrays to C++ binary files, you can use the numpy.ndarray.tofile() function in Python. This function writes the binary data of the numpy array to a file. Here's an example:

import numpy as np

# Create a numpy array
array = np.array([1, 2, 3, 4, 5], dtype=np.int32)

# Write the array to a binary file
array.tofile('test.bin')

In this example, 'test.bin' is the name of the binary file you want to write to, and np.int32 is the data type of the elements in the array. You should replace these with the actual file name and data type according to your specific situation.  Please note that the numpy.ndarray.tofile() function writes the binary data directly to the file without any formatting or metadata. This means that when you read the data back from the file, you need to know the data type and the shape of the array.  In C++, you can read the binary file using std::ifstream in combination with std::vector. Here's an example:


#include <fstream>
#include <vector>

int main() {
    std::ifstream infile("test.bin", std::ios::binary);
    std::vector<int> data;

    // Read the binary data
    int value;
    while (infile.read(reinterpret_cast<char*>(&value), sizeof(int))) {
        data.push_back(value);
    }

    infile.close();

    return 0;
}



In this C++ code, std::ifstream is used to open the binary file, and std::vector<int> is used to store the data read from the file. The std::ifstream::read() function is used to read the binary data from the file. The reinterpret_cast<char*>(&value) is used to convert the pointer to the data to a char*, which is the type of pointer expected by std::ifstream::read(). The sizeof(int) is used to specify the number of bytes to read from the file.


Numpy does not use multiple threads to read binary data. The numpy.fromfile() function, which is used to read binary data into a numpy array, operates in a single-threaded manner. This means it does not take advantage of multiple cores or threads in your CPU to parallelize the reading of binary data.

To take advantage of multiple threads or processes to read data in Python, you can use the concurrent.futures module which provides a high-level interface for asynchronously executing callables.  The approach would be to split the binary file into chunks, and then use a separate thread or process to read each chunk into a numpy array. After all chunks have been read, you can concatenate the arrays to get the final result.  Here is a simple example using concurrent.futures.ThreadPoolExecutor::

    
    import numpy as np
    import concurrent.futures
    import os
    
    def read_chunk(filename, start, end, dtype):
        with open(filename, 'rb') as f:
            f.seek(start)
            data = f.read(end - start)
        return np.frombuffer(data, dtype=dtype)
    
    def read_file_multithreaded(filename, dtype, chunk_size):
        file_size = os.path.getsize(filename)
        starts = list(range(0, file_size, chunk_size))
        ends = starts[1:] + [file_size]
    
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(read_chunk, filename, start, end, dtype) for start, end in zip(starts, ends)]
            arrays = [future.result() for future in concurrent.futures.as_completed(futures)]
    
        return np.concatenate(arrays)
    
    # Usage:
    # array = read_file_multithreaded('test.bin', np.int32, chunk_size=1024*1024)  # 1MB chunks



In this example, read_chunk is a function that reads a chunk of the binary file into a numpy array. read_file_multithreaded is a function that splits the binary file into chunks of a specified size, and uses a thread pool to read each chunk into a numpy array. The numpy arrays are then concatenated to get the final result.  Please note that due to the Global Interpreter Lock (GIL) in Python, using threads may not actually speed up this kind of CPU-bound task. If you find that this is the case, you can use concurrent.futures.ProcessPoolExecutor instead of concurrent.futures.ThreadPoolExecutor to use multiple processes instead of threads. However, using multiple processes has a higher overhead than using threads, so it is more suitable for tasks that take a long time to run.



To perform parallel write operations in Python, you can use the concurrent.futures module, which provides a high-level interface for asynchronously executing callables. The approach would be to split the numpy array into chunks, and then use a separate thread or process to write each chunk to a binary file.  Here is a simple example using concurrent.futures.ThreadPoolExecutor::

    import numpy as np
    import concurrent.futures
    import os
    
    def write_chunk(filename, start, end, array):
        with open(filename, 'ab') as f:
            f.seek(start)
            f.write(array[start:end].tobytes())
    
    def write_file_multithreaded(filename, array, chunk_size):
        array_size = array.size
        starts = list(range(0, array_size, chunk_size))
        ends = starts[1:] + [array_size]
    
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(write_chunk, filename, start, end, array) for start, end in zip(starts, ends)]
            concurrent.futures.wait(futures)
    
    # Usage:
    # array = np.array([...])
    # write_file_multithreaded('test.bin', array, chunk_size=1024*1024)  # 1MB chunks



In this example, write_chunk is a function that writes a chunk of the numpy array to a binary file. write_file_multithreaded is a function that splits the numpy array into chunks of a specified size, and uses a thread pool to write each chunk to a binary file.  Please note that due to the Global Interpreter Lock (GIL) in Python, using threads may not actually speed up this kind of CPU-bound task. If you find that this is the case, you can use concurrent.futures.ProcessPoolExecutor instead of concurrent.futures.ThreadPoolExecutor to use multiple processes instead of threads. However, using multiple processes has a higher overhead than using threads, so it is more suitable for tasks that take a long time to run.


To read and write binary data in C++, you can use the std::ifstream and std::ofstream classes from the <fstream> library. However, C++ does not have built-in support for multithreading or multiprocessing like Python does. You would need to use a library such as OpenMP or the <thread> library in C++11 and later.  Here is a simple example of how you might read and write binary data in C++:


#include <fstream>
#include <vector>

// Function to read binary data
std::vector<char> readBinaryFile(const std::string& filename) {
    // Open the file in binary mode
    std::ifstream file(filename, std::ios::binary);

    // Get the size of the file
    file.seekg(0, std::ios::end);
    std::streamsize size = file.tellg();
    file.seekg(0, std::ios::beg);

    // Read the file into a vector
    std::vector<char> buffer(size);
    if (file.read(buffer.data(), size)) {
        return buffer;
    } else {
        // Handle error
        throw std::runtime_error("Failed to read binary file");
    }
}

// Function to write binary data
void writeBinaryFile(const std::string& filename, const std::vector<char>& data) {
    // Open the file in binary mode
    std::ofstream file(filename, std::ios::binary);

    // Write the data to the file
    if (!file.write(data.data(), data.size())) {
        // Handle error
        throw std::runtime_error("Failed to write binary file");
    }
}


This code does not use multiple threads or processes to read and write the data. If you want to do that, you would need to use a library such as OpenMP or the <thread> library in C++11 and later. However, keep in mind that multithreading or multiprocessing can make the code more complex and may not always result in a performance improvement, depending on the specifics of your use case.



To perform parallel read and write operations in C++ using threads, you can use the <thread> library in C++11 and later. Here is a simple example of how you might read and write binary data in C++ using threads::

    #include <fstream>
    #include <vector>
    #include <thread>
    
    // Function to read binary data
    void readBinaryFile(const std::string& filename, std::vector<char>& buffer) {
        // Open the file in binary mode
        std::ifstream file(filename, std::ios::binary);
    
        // Get the size of the file
        file.seekg(0, std::ios::end);
        std::streamsize size = file.tellg();
        file.seekg(0, std::ios::beg);
    
        // Read the file into a vector
        buffer.resize(size);
        if (!file.read(buffer.data(), size)) {
            // Handle error
            throw std::runtime_error("Failed to read binary file");
        }
    }
    
    // Function to write binary data
    void writeBinaryFile(const std::string& filename, const std::vector<char>& data) {
        // Open the file in binary mode
        std::ofstream file(filename, std::ios::binary);
    
        // Write the data to the file
        if (!file.write(data.data(), data.size())) {
            // Handle error
            throw std::runtime_error("Failed to write binary file");
        }
    }
    
    int main() {
        std::vector<char> buffer1, buffer2;
        std::thread t1(readBinaryFile, "file1.bin", std::ref(buffer1));
        std::thread t2(readBinaryFile, "file2.bin", std::ref(buffer2));
    
        // Wait for the threads to finish
        t1.join();
        t2.join();
    
        // Write the data to the output files
        std::thread t3(writeBinaryFile, "output1.bin", std::ref(buffer1));
        std::thread t4(writeBinaryFile, "output2.bin", std::ref(buffer2));
    
        // Wait for the threads to finish
        t3.join();
        t4.join();
    
        return 0;
    }




In this example, readBinaryFile is a function that reads a binary file into a vector, and writeBinaryFile is a function that writes a vector to a binary file. The main function creates two threads to read two files concurrently, and then creates two more threads to write the data to two output files concurrently. Note that std::ref is used to pass the vectors to the functions by reference, because std::thread passes arguments by value by default.




To optimize the performance of parallel read and write operations in Python, you can consider the following strategies:   
 
Use Asynchronous I/O for I/O-bound tasks: If your program spends a lot of time waiting for I/O operations (like network requests or disk reads/writes), you might get better performance using asynchronous I/O. The asyncio library in Python can help with this.
Here's an example of how you might implement some of these strategies in Python:


import numpy as np
import concurrent.futures
import os

def write_chunk(filename, offset, data):
    with open(filename, 'rb+') as f:
        f.seek(offset)
        f.write(data.tobytes())

def read_chunk(filename, offset, size):
    with open(filename, 'rb') as f:
        f.seek(offset)
        return np.frombuffer(f.read(size), dtype=np.uint8)

def write_file_multithreaded(filename, array, chunk_size):
    with open(filename, 'wb') as f:
        f.write(b'\0' * array.nbytes)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        offset = 0
        while offset < array.nbytes:
            chunk = array[offset:offset+chunk_size]
            executor.submit(write_chunk, filename, offset, chunk)
            offset += chunk_size

def read_file_multithreaded(filename, size, chunk_size):
    array = np.empty(size, dtype=np.uint8)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        offset = 0
        while offset < array.nbytes:
            chunk = executor.submit(read_chunk, filename, offset, chunk_size)
            array[offset:offset+chunk_size] = chunk.result()
            offset += chunk_size

    return array

In this example, write_file_multithreaded and read_file_multithreaded are functions that write and read a numpy array to and from a file using multiple threads. The write_chunk and read_chunk functions are helper functions that write and read a chunk of the numpy array to and from the file.




To optimize the performance of parallel read and write operations in C++, you can consider the following strategies:  
Use Efficient Data Structures: If you're working with large amounts of data, the data structure you use can significantly impact your program's performance. For instance, using std::vector for numerical data can be more efficient than C++ arrays.  
Use Appropriate Libraries: Libraries like <thread> for parallel execution and <fstream> for file operations can help optimize your code.  
Avoid Global Variables: Global variables can be a bottleneck in multi-threaded programs. If your program is CPU-bound (as opposed to being I/O-bound), you might get better performance using local variables instead of global ones.  
Use Buffered I/O: If you're reading or writing large files, using buffered I/O can help improve performance. The built-in std::ifstream and std::ofstream in C++ use buffered I/O by default.  
Reduce Inter-Thread Communication: If you're using multiple threads, try to minimize the amount of data that needs to be shared between them. Inter-thread communication can be slow, so the less data you need to share, the better.  
Use Asynchronous I/O for I/O-bound tasks: If your program spends a lot of time waiting for I/O operations (like disk reads/writes), you might get better performance using asynchronous I/O. The std::async function in C++ can help with this.  
Here's an example of how you might implement some of these strategies in C++:

#include <fstream>
#include <vector>
#include <thread>

// Function to read binary data
void readBinaryFile(const std::string& filename, std::vector<char>& buffer) {
    // Open the file in binary mode
    std::ifstream file(filename, std::ios::binary | std::ios::ate);

    // Get the size of the file
    std::streamsize size = file.tellg();
    file.seekg(0, std::ios::beg);

    // Read the file into a vector
    buffer.resize(size);
    if (!file.read(buffer.data(), size)) {
        // Handle error
        throw std::runtime_error("Failed to read binary file");
    }
}

// Function to write binary data
void writeBinaryFile(const std::string& filename, const std::vector<char>& data) {
    // Open the file in binary mode
    std::ofstream file(filename, std::ios::binary);

    // Write the data to the file
    if (!file.write(data.data(), data.size())) {
        // Handle error
        throw std::runtime_error("Failed to write binary file");
    }
}

int main() {
    std::vector<char> buffer1, buffer2;
    std::thread t1(readBinaryFile, "file1.bin", std::ref(buffer1));
    std::thread t2(readBinaryFile, "file2.bin", std::ref(buffer2));

    // Wait for the threads to finish
    t1.join();
    t2.join();

    // Write the data to the output files
    std::thread t3(writeBinaryFile, "output1.bin", std::ref(buffer1));
    std::thread t4(writeBinaryFile, "output2.bin", std::ref(buffer2));

    // Wait for the threads to finish
    t3.join();
    t4.join();

    return 0;
}


In this example, readBinaryFile is a function that reads a binary file into a vector, and writeBinaryFile is a function that writes a vector to a binary file. The main function creates two threads to read two files concurrently, and then creates two more threads to write the data to two output files concurrently. Note that std::ref is used to pass the vectors to the functions by reference, because std::thread passes arguments by value by default.


In both Python and C++, you can handle errors during file operations using exception handling mechanisms.  In Python, you can use a try/except block to catch and handle exceptions. Here's an example:

    
    def read_binary_file(filename):
        try:
            with open(filename, 'rb') as f:
                data = f.read()
            return data
        except FileNotFoundError:
            print(f"File {filename} not found.")
        except IOError:
            print(f"Error occurred while reading the file {filename}.")
    
    def write_binary_file(filename, data):
        try:
            with open(filename, 'wb') as f:
                f.write(data)
        except IOError:
            print(f"Error occurred while writing to the file {filename}.")



In C++, you can use try/catch blocks to handle exceptions. However, by default, C++ I/O operations do not throw exceptions when they fail. You need to enable exceptions for a file stream by calling the exceptions() method. Here's an example:

    #include <fstream>
    #include <iostream>
    
    void read_binary_file(const std::string& filename, std::vector<char>& buffer) {
        std::ifstream file(filename, std::ios::binary | std::ios::ate);
        file.exceptions(std::ifstream::failbit | std::ifstream::badbit);
        try {
            std::streamsize size = file.tellg();
            file.seekg(0, std::ios::beg);
            buffer.resize(size);
            file.read(buffer.data(), size);
        } catch (std::ifstream::failure& e) {
            std::cerr << "Exception occurred while reading the file " << filename << "\n";
        }
    }
    
    void write_binary_file(const std::string& filename, const std::vector<char>& data) {
        std::ofstream file(filename, std::ios::binary);
        file.exceptions(std::ofstream::failbit | std::ofstream::badbit);
        try {
            file.write(data.data(), data.size());
        } catch (std::ofstream::failure& e) {
            std::cerr << "Exception occurred while writing to the file " << filename << "\n";
        }
    }

In these examples, if an error occurs during the read or write operation, an exception is thrown and caught, and an error message is printed to the console. You can replace the print statements with any error handling code that is appropriate for your application.


In Python, you can use the try/except block within your parallel read and write functions to handle any exceptions that might occur during the execution of these operations. Here's an example of how you can do this:

    import concurrent.futures
    
    def read_file_multithreaded(filename, size, chunk_size):
        try:
            with open(filename, 'rb') as f:
                data = f.read()
            return data
        except FileNotFoundError:
            print(f"File {filename} not found.")
        except IOError:
            print(f"Error occurred while reading the file {filename}.")
    
    def write_file_multithreaded(filename, data):
        try:
            with open(filename, 'wb') as f:
                f.write(data)
        except IOError:
            print(f"Error occurred while writing to the file {filename}.")
    
    # Using ThreadPoolExecutor to read and write files in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_file = {executor.submit(read_file_multithreaded, file, size, chunk_size): file for file in files}
        for future in concurrent.futures.as_completed(future_to_file):
            file = future_to_file[future]
            try:
                data = future.result()
            except Exception as exc:
                print(f'{file} generated an exception: {exc}')


In C++, you can use try/catch blocks to handle exceptions. However, by default, C++ I/O operations do not throw exceptions when they fail. You need to enable exceptions for a file stream by calling the exceptions() method. Here's an example:

#include <fstream>
#include <iostream>
#include <vector>
#include <thread>

void read_binary_file(const std::string& filename, std::vector<char>& buffer) {
    std::ifstream file(filename, std::ios::binary | std::ios::ate);
    file.exceptions(std::ifstream::failbit | std::ifstream::badbit);
    try {
        std::streamsize size = file.tellg();
        file.seekg(0, std::ios::beg);
        buffer.resize(size);
        if (!file.read(buffer.data(), size)) {
            // Handle error
        }
    } catch (std::ifstream::failure& e) {
        std::cerr << "Exception occurred while reading the file " << filename << "\n";
    }
}

void write_binary_file(const std::string& filename, const std::vector<char>& data) {
    std::ofstream file(filename, std::ios::binary);
    file.exceptions(std::ofstream::failbit | std::ofstream::badbit);
    try {
        if (!file.write(data.data(), data.size())) {
            // Handle error
        }
    } catch (std::ofstream::failure& e) {
        std::cerr << "Exception occurred while writing to the file " << filename << "\n";
    }
}


In these examples, if an error occurs during the read or write operation, an exception is thrown and caught, and an error message is printed to the console. You can replace the print statements with any error handling code that is appropriate for your application



#tom;
Here is a simple example of how you can read, modify, and write back to a TOML file using the tomlplusplus library in C++.


#include <iostream>
#include <fstream>
#include <toml++/toml.h>

int main() {
    // Read the TOML file
    auto config = toml::parse_file("config.toml");

    // Get and modify the variables
    auto parameter1 = toml::find<std::string>(config, "parameter1");
    std::cout << "Old parameter1: " << parameter1 << std::endl;
    parameter1 = "new value";
    std::cout << "New parameter1: " << parameter1 << std::endl;

    // Write back to the TOML file
    std::ofstream file("config.toml");
    file << config;

    return 0;
}

This code reads a TOML file named config.toml, retrieves a string value associated with the key parameter1, modifies it, and then writes the updated configuration back to the file. Please replace "config.toml" and "parameter1" with your actual file path and variable name.  Please note that you need to install the tomlplusplus library in your C++ environment to use it. You can find it here: https://github.com/marzer/tomlplusplus.

here is an example of how you can create a TOML file with the tomlplusplus library in C++. This file will contain a double, an integer, a string, a list of integers, and a dictionary of strings to doubles.

#include <iostream>
#include <fstream>
#include <toml++/toml.h>

int main() {
    // Create a new TOML table
    toml::table config;

    // Add a double
    config.insert_or_assign("double_value", 1.23);

    // Add an integer
    config.insert_or_assign("integer_value", 123);

    // Add a string
    config.insert_or_assign("string_value", "Hello, World!");

    // Add a list of integers
    config.insert_or_assign("list_of_integers", toml::array{1, 2, 3, 4, 5});

    // Add a dictionary of strings to doubles
    toml::table dict;
    dict.insert_or_assign("key1", 1.1);
    dict.insert_or_assign("key2", 2.2);
    dict.insert_or_assign("key3", 3.3);
    config.insert_or_assign("dictionary", dict);

    // Write the TOML table to a file
    std::ofstream file("config.toml");
    file << config;

    return 0;
}

To read the TOML file back in C++, you can use the toml::parse function from the tomlplusplus library. Here is an example::

    #include <iostream>
    #include <toml++/toml.h>
    
    int main() {
        // Parse the TOML file
        auto config = toml::parse("config.toml");
    
        // Retrieve the values
        double double_value = toml::find<double>(config, "double_value");
        int integer_value = toml::find<int>(config, "integer_value");
        std::string string_value = toml::find<std::string>(config, "string_value");
        std::vector<int> list_of_integers = toml::find<std::vector<int>>(config, "list_of_integers");
        auto dictionary = toml::find<toml::table>(config, "dictionary");
    
        // Print the values
        std::cout << "Double: " << double_value << std::endl;
        std::cout << "Integer: " << integer_value << std::endl;
        std::cout << "String: " << string_value << std::endl;
        std::cout << "List of integers: ";
        for (int i : list_of_integers) {
            std::cout << i << " ";
        }
        std::cout << std::endl;
        std::cout << "Dictionary: " << std::endl;
        for (const auto& [key, value] : dictionary) {
            std::cout << key << ": " << *value.as<double>() << std::endl;
        }
    
        return 0;
    }



# Sqlite
To create and write to an SQLite database in C++, you can use the SQLite C/C++ interface. Here's a step-by-step plan:  
* Include the SQLite library in your project.
* Open a connection to the SQLite database using sqlite3_open.
* Create a table in the database using sqlite3_exec.
* Insert data into the table using sqlite3_exec.
* Close the connection to the database using sqlite3_close.


    #include <sqlite3.h>
    #include <stdio.h>

    void createTableAndInsertData() {
    sqlite3* db;
    char* errMsg = 0;
    int rc;

    // Open database
    rc = sqlite3_open("test.db", &db);
    if (rc != SQLITE_OK) {
        std::cerr << "Cannot open database: " << sqlite3_errmsg(db) << std::endl;
        return;
    }

    // SQL to create table and insert data
    const char* sql =
        "CREATE TABLE IF NOT EXISTS Cars(Id INT, Name TEXT, Price INT);"
        "INSERT INTO Cars VALUES(1, 'Audi', 52642);"
        "INSERT INTO Cars VALUES(2, 'Mercedes', 57127);"
        "INSERT INTO Cars VALUES(3, 'Skoda', 9000);"
        "INSERT INTO Cars VALUES(4, 'Volvo', 29000);";

    // Execute SQL
    rc = sqlite3_exec(db, sql, 0, 0, &errMsg);
    if (rc != SQLITE_OK ) {
        std::cerr << "SQL error: " << errMsg << std::endl;
        sqlite3_free(errMsg);
    } else {
        std::cout << "Table created and data inserted successfully" << std::endl;
    }

    // Close database
    sqlite3_close(db);
}


    void readDataFromDatabase() {
    /*
    This function opens a connection to a SQLite database named test.db, selects all rows from a table named Cars, and then prints the data to the console. If there's an error during any of these operations, it prints an error message to the console. The database connection is always closed at the end of the function using sqlite3_close.
    */
        sqlite3* db;
        char* errMsg = 0;
        int rc;

        // Open database
        rc = sqlite3_open("test.db", &db);
        if (rc != SQLITE_OK) {
            std::cerr << "Cannot open database: " << sqlite3_errmsg(db) << std::endl;
            return;
        }

        // SQL to select data
        const char* sql = "SELECT * FROM Cars;";

        // Callback function to print the data
        auto callback = [](void*, int count, char** data, char** columns) -> int {
            for (int i = 0; i < count; i++) {
                std::cout << columns[i] << " = " << (data[i] ? data[i] : "NULL") << std::endl;
            }
            std::cout << std::endl;
            return 0;
        };

        // Execute SQL
        rc = sqlite3_exec(db, sql, callback, 0, &errMsg);
        if (rc != SQLITE_OK ) {
            std::cerr << "SQL error: " << errMsg << std::endl;
            sqlite3_free(errMsg);
        }

        // Close database
        sqlite3_close(db);
    }

This code creates a new SQLite database file named test.db, creates a table named Cars with columns Id, Name, and Price, and inserts four rows of data into the table. If the database file already exists, it opens the existing file. If the Cars table already exists, it drops the table before creating a new one.

Please make sure to have the SQLite library installed and linked to your project.



## pybind11

    #include <pybind11/pybind11.h>
    #include <pybind11/numpy.h>

    namespace py = pybind11;

    py::array_t<double> create_numpy_array() {
        // Create a C++ array
        std::vector<double> c_array = {1.0, 2.0, 3.0, 4.0, 5.0};

        // Convert the C++ array to a NumPy array
        py::array_t<double> numpy_array(c_array.size(), c_array.data());

        return numpy_array;
    }

    PYBIND11_MODULE(example, m) {
    m.def("create_numpy_array", &create_numpy_array, "A function that creates a NumPy array");
    }

# C-API
To pass a NumPy array between C++ and Python using the C-API, you can use the PyArray_SimpleNewFromData function from the NumPy C-API. This function creates a NumPy array object from a pointer to the data, the dimensions of the array, and the data type.  Here is an example of how you can do this:  First, you need to include the necessary headers::

    #include <Python.h>
    #define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
    #include <numpy/arrayobject.h>



Then, you can create a function that creates a NumPy array from a C++ array:

    PyObject* create_numpy_array() {
        // Create a C++ array
        double c_array[] = {1.0, 2.0, 3.0, 4.0, 5.0};

        // Convert the C++ array to a NumPy array
        npy_intp dimensions[] = {5};
        PyObject* numpy_array = PyArray_SimpleNewFromData(1, dimensions, NPY_DOUBLE, c_array);

        return numpy_array;
    }

In this example, PyArray_SimpleNewFromData is used to create a NumPy array from the C++ array c_array. The 1 is the number of dimensions of the array, dimensions is an array of the size of each dimension, NPY_DOUBLE is the data type of the array, and c_array is the pointer to the data.  Please note that you need to initialize the NumPy C-API using import_array() before you can use PyArray_SimpleNewFromData. You can do this in the initialization function of your module::

    PyMODINIT_FUNC PyInit_mymodule(void) {
        PyObject* m;

        static struct PyModuleDef moduledef = {
            PyModuleDef_HEAD_INIT,
            "mymodule",
            NULL,
            -1,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL
        };

        m = PyModule_Create(&moduledef);
        if (m == NULL)
            return NULL;

        // Initialize the NumPy C-API
        import_array();

        // Add the create_numpy_array function to the module
        PyModule_AddObject(m, "create_numpy_array", PyCFunction_New(&create_numpy_array, NULL));

        return m;
    }


pybind11
=========
