#include <string>
#include <map>
#include <exception>

class TengineError: public std::exception {
private:
    mutable std::string msg;
    std::map<std::string, std::string> kwargs;
    mutable std::string message;

public:
    TengineError(std::map<std::string, std::string> kwargs) : kwargs(kwargs) { }

    void set_msg(const std::string& new_msg) {
        this->msg = new_msg;
    }

    void construct_message() const {
        this->msg = "The base message where to replace kwargs"; // Should be replaced by your base message
        for(const auto& [key, value] : kwargs) {
            size_t start_pos = 0;
            std::string to_replace = "{" + key + "}";
            while((start_pos = msg.find(to_replace, start_pos)) != std::string::npos) {
                msg.replace(start_pos, to_replace.length(), value);
                start_pos += value.length();
            }
        }
        this->message = this->msg;
    }

    const char* what() const noexcept override {
        if (this->message.empty()) {
            this->construct_message();
        }
        return this->message.c_str();
    }
};

class NoTradeDataAvailable : public TengineError {
public:
    using TengineError::TengineError; // Inherit constructors
};

class NoTradeDataAvailableTooEarly : public NoTradeDataAvailable {
public:
    NoTradeDataAvailableTooEarly(std::map<std::string, std::string> kwargs) : NoTradeDataAvailable(kwargs) {
        this->set_msg("{sid} does not exist on {dt}. It started trading on {start_dt}.");
    }
};

class NoTradeDataAvailableTooLate : public NoTradeDataAvailable {
public:
    NoTradeDataAvailableTooLate(std::map<std::string, std::string> kwargs) : NoTradeDataAvailable(kwargs) {
        this->set_msg("{sid} does not exist on {dt}. It stopped trading on {end_dt}.");
    }
};

class BenchmarkAssetNotAvailableTooEarly : public NoTradeDataAvailableTooEarly {
public:
    using NoTradeDataAvailableTooEarly::NoTradeDataAvailableTooEarly; // Inherit constructors
};

class BenchmarkAssetNotAvailableTooLate : public NoTradeDataAvailableTooLate {
public:
    using NoTradeDataAvailableTooLate::NoTradeDataAvailableTooLate; // Inherit constructors
};

class InvalidBenchmarkAsset : public TengineError {
public:
    InvalidBenchmarkAsset(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{sid} cannot be used as the benchmark because it has a stock dividend on {dt}.  Choose another asset to use as the benchmark.");
    }
};

class WrongDataForTransform : public TengineError {
public:
    WrongDataForTransform(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{transform} requires {fields}. Event cannot be processed.");
    }
};

class UnsupportedSlippageModel : public TengineError {
public:
    UnsupportedSlippageModel(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("You attempted to set slippage with an unsupported class. Please use VolumeShareSlippage or FixedSlippage.");
    }
};

class IncompatibleSlippageModel : public TengineError {
public:
    IncompatibleSlippageModel(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("You attempted to set an incompatible slippage model for {asset_type}. The slippage model '{given_model}' only supports {supported_asset_types}.");
    }
};

class SetSlippagePostInit : public TengineError {
public:
    SetSlippagePostInit(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("You attempted to set slippage outside of `initialize`. You may only call 'set_slippage' in your initialize method.");
    }
};

class SetCancelPolicyPostInit : public TengineError {
public:
    SetCancelPolicyPostInit(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("You attempted to set the cancel policy outside of `initialize`. You may only call 'set_cancel_policy' in your initialize method.");
    }
};

class RegisterTradingControlPostInit : public TengineError {
public:
    RegisterTradingControlPostInit(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("You attempted to set a trading control outside of `initialize`. Trading controls may only be set in your initialize method.");
    }
};



class RegisterAccountControlPostInit : public TengineError {
public:
    RegisterAccountControlPostInit(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("You attempted to set an account control outside of `initialize`. Account controls may only be set in your initialize method.");
    }
};

class UnsupportedCommissionModel : public TengineError {
public:
    UnsupportedCommissionModel(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("You attempted to set commission with an unsupported class. Please use PerShare or PerTrade.");
    }
};

class IncompatibleCommissionModel : public TengineError {
public:
    IncompatibleCommissionModel(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("You attempted to set an incompatible commission model for {asset_type}. The commission model '{given_model}' only supports {supported_asset_types}.");
    }
};

class UnsupportedCancelPolicy : public TengineError {
public:
    UnsupportedCancelPolicy(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("You attempted to set the cancel policy with an unsupported class.  Please use an instance of CancelPolicy.");
    }
};

class SetCommissionPostInit : public TengineError {
public:
    SetCommissionPostInit(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("You attempted to override commission outside of `initialize`. You may only call 'set_commission' in your initialize method.");
    }
};

class TransactionWithNoVolume : public TengineError {
public:
    TransactionWithNoVolume(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Transaction {txn} has a volume of zero.");
    }
};

class TransactionWithWrongDirection : public TengineError {
public:
    TransactionWithWrongDirection(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Transaction {txn} not in same direction as corresponding order {order}.");
    }
};

class TransactionWithNoAmount : public TengineError {
public:
    TransactionWithNoAmount(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Transaction {txn} has an amount of zero.");
    }
};

class TransactionVolumeExceedsOrder : public TengineError {
public:
    TransactionVolumeExceedsOrder(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Transaction volume of {txn} exceeds the order volume of {order}.");
    }
};

class UnsupportedOrderParameters : public TengineError {
public:
    UnsupportedOrderParameters(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{msg}");
    }
};

class CannotOrderDelistedAsset : public TengineError {
public:
    CannotOrderDelistedAsset(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{msg}");
    }
};

class BadOrderParameters : public TengineError {
public:
    BadOrderParameters(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{msg}");
    }
};

class OrderDuringInitialize : public TengineError {
public:
    OrderDuringInitialize(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{msg}");
    }
};

class SetBenchmarkOutsideInitialize : public TengineError {
public:
    SetBenchmarkOutsideInitialize(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("'set_benchmark' can only be called within initialize function.");
    }
};

class ZeroCapitalError : public TengineError {
public:
    ZeroCapitalError(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("initial capital base must be greater than zero");
    }
};

class AccountControlViolation : public TengineError {
public:
    AccountControlViolation(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Account violates account constraint {constraint}.");
    }
};

class TradingControlViolation : public TengineError {
public:
    TradingControlViolation(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Order for {amount} shares of {asset} at {datetime} violates trading constraint {constraint}.");
    }
};

class IncompatibleHistoryFrequency : public TengineError {
public:
    IncompatibleHistoryFrequency(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Requested history at frequency '{frequency}' cannot be created with data at frequency '{data_frequency}'.");
    }
};

class OrderInBeforeTradingStart : public TengineError {
public:
    OrderInBeforeTradingStart(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Cannot place orders inside before_trading_start.");
    }
};

class MultipleSymbolsFound : public TengineError {
public:
    MultipleSymbolsFound(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Multiple symbols with the name '{symbol}' found. Use the as_of_date' argument to specify when the date symbol-lookup should be valid. Possible options: {options}");
    }
};

class MultipleSymbolsFoundForFuzzySymbol : public MultipleSymbolsFound {
public:
    MultipleSymbolsFoundForFuzzySymbol(std::map<std::string, std::string> kwargs) : MultipleSymbolsFound(kwargs) {
        this->set_msg("Multiple symbols were found fuzzy matching the name '{symbol}'. Use the as_of_date and/or country_code arguments to specify the date and country for the symbol-lookup. Possible options: {options}");
    }
};

class SameSymbolUsedAcrossCountries : public MultipleSymbolsFound {
public:
    SameSymbolUsedAcrossCountries(std::map<std::string, std::string> kwargs) : MultipleSymbolsFound(kwargs) {
        this->set_msg("The symbol '{symbol}' is used in more than one country. Use the country_code argument to specify the country. Possible options by country: {options}");
    }
};

class SymbolNotFound : public TengineError {
public:
    SymbolNotFound(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Symbol '{symbol}' was not found.");
    }
};

class RootSymbolNotFound : public TengineError {
public:
    RootSymbolNotFound(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Root symbol '{root_symbol}' was not found.");
    }
};

class ValueNotFoundForField : public TengineError {
public:
    ValueNotFoundForField(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Value '{value}' was not found for field '{field}'.");
    }
};

class MultipleValuesFoundForField : public TengineError {
public:
    MultipleValuesFoundForField(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Multiple occurrences of the value '{value}' found for field '{field}'. Use the 'as_of_date' or 'country_code' argument to specify when or where the lookup should be valid. Possible options: {options}");
    }
};

class NoValueForSid : public TengineError {
public:
    NoValueForSid(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("No '{field}' value found for sid '{sid}'.");
    }
};

class MultipleValuesFoundForSid : public TengineError {
public:
    MultipleValuesFoundForSid(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Multiple '{field}' values found for sid '{sid}'. Use the as_of_date' argument to specify when the lookup should be valid. Possible options: {options}");
    }
};

class SidsNotFound : public TengineError {
public:
    SidsNotFound(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        if (kwargs["sids"].size() > 1) {
            this->set_msg("No assets found for sids: {sids}.");
        } else {
            this->set_msg("No asset found for sid: {sids[0]}.");
        }
    }
};

class EquitiesNotFound : public SidsNotFound {
public:
    EquitiesNotFound(std::map<std::string, std::string> kwargs) : SidsNotFound(kwargs) {
        if (kwargs["sids"].size() > 1) {
            this->set_msg("No equities found for sids: {sids}.");
        } else {
            this->set_msg("No equity found for sid: {sids[0]}.");
        }
    }
};

class FutureContractsNotFound : public SidsNotFound {
public:
    FutureContractsNotFound(std::map<std::string, std::string> kwargs) : SidsNotFound(kwargs) {
        if (kwargs["sids"].size() > 1) {
            this->set_msg("No future contracts found for sids: {sids}.");
        } else {
            this->set_msg("No future contract found for sid: {sids[0]}.");
        }
    }
};

class ConsumeAssetMetaDataError : public TengineError {
public:
    ConsumeAssetMetaDataError(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("AssetFinder can not consume metadata of type {obj}. Metadata must be a dict, a DataFrame, or a tables.Table. If the provided metadata is a Table, the rows must contain both or one of 'sid' or 'symbol'.");
    }
};

class SidAssignmentError : public TengineError {
public:
    SidAssignmentError(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("AssetFinder metadata is missing a SID for identifier '{identifier}'.");
    }
};

class NoSourceError : public TengineError {
public:
    NoSourceError(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("No data source given.");
    }
};

class PipelineDateError : public TengineError {
public:
    PipelineDateError(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Only one simulation date given. Please specify both the 'start' and 'end' for the simulation, or neither. If neither is given, the start and end of the DataSource will be used. Given start = '{start}', end = '{end}'");
    }
};

class WindowLengthTooLong : public TengineError {
public:
    WindowLengthTooLong(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Can't construct a rolling window of length {window_length} on an array of length {nrows}.");
    }
};

class WindowLengthNotPositive : public TengineError {
public:
    WindowLengthNotPositive(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Expected a window_length greater than 0, got {window_length}.");
    }
};

class NonWindowSafeInput : public TengineError {
public:
    NonWindowSafeInput(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Can't compute windowed expression {parent} with windowed input {child}.");
    }
};

class TermInputsNotSpecified : public TengineError {
public:
    TermInputsNotSpecified(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{termname} requires inputs, but no inputs list was passed.");
    }
};

class NonPipelineInputs : public TengineError {
public:
    NonPipelineInputs(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Unexpected input types in {}. Inputs to Pipeline expressions must be Filters, Factors, Classifiers, or BoundColumns. Got the following type(s) instead: {}");
    }
};

class TermOutputsEmpty : public TengineError {
public:
    TermOutputsEmpty(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{termname} requires at least one output when passed an outputs argument.");
    }
};

class InvalidOutputName : public TengineError {
public:
    InvalidOutputName(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{output_name!r} cannot be used as an output name for {termname}. Output names cannot start with an underscore or be contained in the following list: {disallowed_names}.");
    }
};

class WindowLengthNotSpecified : public TengineError {
public:
    WindowLengthNotSpecified(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{termname} requires a window_length, but no window_length was passed.");
    }
};

class InvalidTermParams : public TengineError {
public:
    InvalidTermParams(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Expected a list of strings as a class-level attribute for {termname}.params, but got {value} instead.");
    }
};

class DTypeNotSpecified : public TengineError {
public:
    DTypeNotSpecified(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{termname} requires a dtype, but no dtype was passed.");
    }
};

class NotDType : public TengineError {
public:
    NotDType(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{termname} expected a numpy dtype object for a dtype, but got {dtype} instead.");
    }
};

class UnsupportedDType : public TengineError {
public:
    UnsupportedDType(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Failed to construct {termname}. Pipeline terms of dtype {dtype} are not yet supported.");
    }
};

class BadPercentileBounds : public TengineError {
public:
    BadPercentileBounds(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Percentile bounds must fall between 0.0 and {upper_bound}, and min must be less than max. Inputs were min={min_percentile}, max={max_percentile}.");
    }
};

class UnknownRankMethod : public TengineError {
public:
    UnknownRankMethod(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Unknown ranking method: '{method}'. `method` must be one of {choices}");
    }
};

class AttachPipelineAfterInitialize : public TengineError {
public:
    AttachPipelineAfterInitialize(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Attempted to attach a pipeline after initialize(). attach_pipeline() can only be called during initialize.");
    }
};

class PipelineOutputDuringInitialize : public TengineError {
public:
    PipelineOutputDuringInitialize(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Attempted to call pipeline_output() during initialize. pipeline_output() can only be called once initialize has completed.");
    }
};

class NoSuchPipeline : public TengineError {
public:
    NoSuchPipeline(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("No pipeline named '{name}' exists. Valid pipeline names are {valid}. Did you forget to call attach_pipeline()?");
    }
};

class DuplicatePipelineName : public TengineError {
public:
    DuplicatePipelineName(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Attempted to attach pipeline named {name!r}, but the name already exists for another pipeline. Please use a different name for this pipeline.");
    }
};

class UnsupportedDataType : public TengineError {
public:
    UnsupportedDataType(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{typename} instances with dtype {dtype} are not supported.{hint}");
    }
};

class NoFurtherDataError : public TengineError {
public:
    NoFurtherDataError(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{msg}");
    }
};

class UnsupportedDatetimeFormat : public TengineError {
public:
    UnsupportedDatetimeFormat(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("The input '{input}' passed to '{method}' is not coercible to a pandas.Timestamp object.");
    }
};

class AssetDBVersionError : public TengineError {
public:
    AssetDBVersionError(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("The existing Asset database has an incorrect version: {db_version}. Expected version: {expected_version}. Try rebuilding your asset database or updating your version of Tengine.");
    }
};

class AssetDBImpossibleDowngrade : public TengineError {
public:
    AssetDBImpossibleDowngrade(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("The existing Asset database is version: {db_version} which is lower than the desired downgrade version: {desired_version}.");
    }
};

class HistoryWindowStartsBeforeData : public TengineError {
public:
    HistoryWindowStartsBeforeData(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("History window extends before {first_trading_day}. To use this history window, start the backtest on or after {suggested_start_day}.");
    }
};

class NonExistentAssetInTimeFrame : public TengineError {
public:
    NonExistentAssetInTimeFrame(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("The target asset '{asset}' does not exist for the entire timeframe between {start_date} and {end_date}.");
    }
};

class InvalidCalendarName : public TengineError {
public:
    InvalidCalendarName(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("The requested Calendar, {calendar_name}, does not exist.");
    }
};

class CalendarNameCollision : public TengineError {
public:
    CalendarNameCollision(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("A calendar with the name {calendar_name} is already registered.");
    }
};

class CyclicCalendarAlias : public TengineError {
public:
    CyclicCalendarAlias(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Cycle in calendar aliases: [{cycle}]");
    }
};

class ScheduleFunctionWithoutCalendar : public TengineError {
public:
    ScheduleFunctionWithoutCalendar(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("To use schedule_function, the TradingAlgorithm must be running on an ExchangeTradingSchedule, rather than {schedule}.");
    }
};

class ScheduleFunctionInvalidCalendar : public TengineError {
public:
    ScheduleFunctionInvalidCalendar(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Invalid calendar '{given_calendar}' passed to schedule_function. Allowed options are {allowed_calendars}.");
    }
};

class UnsupportedPipelineOutput : public TengineError {
public:
    UnsupportedPipelineOutput(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Cannot add column {column_name!r} with term {term}. Adding slices or single-column-output terms as pipeline columns is not currently supported.");
    }
};

class NonSliceableTerm : public TengineError {
public:
    NonSliceableTerm(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("Taking slices of {term} is not currently supported.");
    }
};

class IncompatibleTerms : public TengineError {
public:
    IncompatibleTerms(std::map<std::string, std::string> kwargs) : TengineError(kwargs) {
        this->set_msg("{term_1} and {term_2} must have the same mask in order to compute correlations and regressions asset-wise.");
    }
};

