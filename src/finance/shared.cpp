#include <type_traits>
#include <tuple>

// Base class for all financial models
class FinancialModel {
public:
    virtual ~FinancialModel() = default;
};

// Marker class for allowed asset types
template <typename... AssetTypes>
class AllowedAssetMarker : public FinancialModel {
public:
    using AllowedAssetTypes = std::tuple<AssetTypes...>;
};

// Base class for all equity models
class EquityModel : public AllowedAssetMarker<Equity> {
    // Implementation...
};

// Base class for all future models
class FutureModel : public AllowedAssetMarker<Future> {
    // Implementation...
};

// Custom slippage model
template <typename... Models>
class MyCustomSlippage : public Models... {
public:
    using AllowedAssetTypes = typename std::tuple_cat<typename Models::AllowedAssetTypes...>;

    void process_order(Data data, Order order) {
        // Implementation...
    }
};

