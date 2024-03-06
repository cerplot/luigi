import DataLayer

source = DataLayer.SpecificDataSource()
layer = DataLayer.DataLayer()
layer.addProvider(source)

tick = layer.getTick()