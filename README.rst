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

As you can see, C++ optionally saves intermediate data after each layer,
 and the next layer can read that data and do its work just by using that data.
In the future, we can use python to read and write those saved c++ data as well.
This will be important for researching different ideas in the future.
So research will be done in python, and then the best ideas will be implemented in C++.
This is an optimal combination of performance and flexibility. It is not required to
know C++ to do research, but it is required to know C++ to implement the best ideas in the production code.


For configuration, we will use toml file. https://toml.io/en/
This is a simple format that python can read natively and C++ has a good library for it as well.
(e.g. https://marzer.github.io/tomlplusplus/). There is no need to create our own configuration file format. We will talk about the content of the configuration file later. For now let's just say that it will contain the paths to the data, the list of stocks, the list of indicators, and some other parameters that we will need in the future.

A Build system is CMake that is standard nowadays.
And if in the future you want to compile the code on windows, it will be easy to make that transition. And possibly some might want to use Windows for development, and CMake will make that transition smooth.


In the future, we might need python access to the C++ internals (calling C++ functions from python, for example).
As a first step, we don't need to worry about this, but later we will need to think about how to do this. Keep in mind that this will be needed at some point.
pybind11 - can be used for these purposes (open for other suggestions, but it seems like the best choice these days).


Also, MLK (https://www.intel.com/content/www/us/en/developer/tools/oneapi/onemkl.html) will be used at some point. We should be able to compile it.

Another library we will need is sqlite. Stats and other outputs will be saved in a sqlite database.

Version control is git. Later we can decide to choose another branching strategy.
But, for now, we will keep things simple:
- master branch is always stable and can be deployed to production.
- development branch is used for development.
- feature branches are used for developing new features. and are merged into the development branch when the feature is ready.


Unit tests are done with google test (C++) (if there is no objection) and pytest (python).
compiler is gcc (open for other suggestions, but it seems to be the standard choice).
clang-format is used for code formatting.

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