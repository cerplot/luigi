std::vector<Asset> make_rotating_equity_info(
        int num_assets,
        std::chrono::system_clock::time_point first_start,
        std::chrono::duration<int> frequency,
        int periods_between_starts,
        int asset_lifetime,
        std::string exchange = "TEST"
) {
    std::vector<Asset> assets;
    assets.reserve(num_assets);
    for (int i = 0; i < num_assets; ++i) {
        Asset asset;
        asset.symbol = 'A' + i;
        asset.start_date = first_start + std::chrono::duration<int>(i * periods_between_starts) * frequency;
        asset.end_date = asset.start_date + std::chrono::duration<int>(asset_lifetime) * frequency;
        asset.exchange = exchange;
        assets.push_back(asset);
    }
    return assets;
}

std::vector<AssetInfo> make_simple_equity_info(
        std::vector<int> sids,
        std::chrono::system_clock::time_point start_date,
        std::chrono::system_clock::time_point end_date,
        std::vector<std::string> symbols = {},
        std::vector<std::string> names = {},
        std::string exchange = "TEST"
) {
    int num_assets = sids.size();
    if (symbols.empty()) {
        for (int i = 0; i < num_assets; ++i) {
            symbols.push_back(std::string(1, 'A' + i));
        }
    }

    if (names.empty()) {
        for (const auto& symbol : symbols) {
            names.push_back(symbol + " INC.");
        }
    }

    std::vector<AssetInfo> info;
    for (int i = 0; i < num_assets; ++i) {
        AssetInfo asset;
        asset.symbol = symbols[i];
        asset.start_date = start_date;
        asset.end_date = end_date;
        asset.asset_name = names[i];
        asset.exchange = exchange;
        info.push_back(asset);
    }

    return info;
}

std::vector<AssetInfo> make_simple_multi_country_equity_info(
        std::map<std::string, std::vector<int>> countries_to_sids,
        std::map<std::string, std::string> countries_to_exchanges,
        std::chrono::system_clock::time_point start_date,
        std::chrono::system_clock::time_point end_date
) {
    std::vector<int> sids;
    std::vector<std::string> symbols;
    std::vector<std::string> exchanges;

    for (const auto& country_sids : countries_to_sids) {
        std::string country = country_sids.first;
        std::string exchange = countries_to_exchanges[country];
        for (int i = 0; i < country_sids.second.size(); ++i) {
            int sid = country_sids.second[i];
            sids.push_back(sid);
            symbols.push_back(country + "-" + std::to_string(i));
            exchanges.push_back(exchange);
        }
    }

    std::vector<AssetInfo> info;
    for (int i = 0; i < sids.size(); ++i) {
        AssetInfo asset;
        asset.symbol = symbols[i];
        asset.start_date = start_date;
        asset.end_date = end_date;
        asset.asset_name = symbols[i];
        asset.exchange = exchanges[i];
        info.push_back(asset);
    }

    return info;
}

std::vector<AssetInfo> make_jagged_equity_info(
        int num_assets,
        std::chrono::system_clock::time_point start_date,
        std::chrono::system_clock::time_point first_end,
        std::chrono::duration<int> frequency,
        int periods_between_ends,
        std::chrono::duration<int> auto_close_delta
) {
    std::vector<AssetInfo> info;
    for (int i = 0; i < num_assets; ++i) {
        AssetInfo asset;
        asset.symbol = std::string(1, 'A' + i);
        asset.start_date = start_date;
        asset.end_date = first_end + std::chrono::duration<int>(i * periods_between_ends) * frequency;
        asset.exchange = "TEST";
        if (auto_close_delta.count() != 0) {
            asset.auto_close_date = asset.end_date + auto_close_delta;
        }
        info.push_back(asset);
    }

    return info;
}


std::vector<FutureInfo> make_future_info(
        int first_sid,
        std::vector<std::string> root_symbols,
        std::vector<int> years,
        std::function<std::chrono::system_clock::time_point(std::chrono::system_clock::time_point)> notice_date_func,
        std::function<std::chrono::system_clock::time_point(std::chrono::system_clock::time_point)> expiration_date_func,
        std::function<std::chrono::system_clock::time_point(std::chrono::system_clock::time_point)> start_date_func,
        std::map<std::string, int> month_codes = {}, // Default value to be replaced with actual month codes
        int multiplier = 500
) {
    if (month_codes.empty()) {
        // month_codes = CMES_CODE_TO_MONTH; // Replace with actual month codes
    }

    std::vector<std::string> year_strs(years.size());
    std::transform(years.begin(), years.end(), year_strs.begin(), [](int year) { return std::to_string(year); });

    std::vector<FutureInfo> contracts;
    int sid = first_sid;
    for (const auto& root_sym : root_symbols) {
        for (const auto& year_str : year_strs) {
            for (const auto& month_code : month_codes) {
                std::string suffix = month_code.first + year_str.substr(year_str.size() - 2);
                std::chrono::system_clock::time_point month_begin; // Calculate month_begin based on year and month_code.second

                FutureInfo contract;
                contract.sid = sid++;
                contract.root_symbol = root_sym;
                contract.symbol = root_sym + suffix;
                contract.start_date = start_date_func(month_begin);
                contract.notice_date = notice_date_func(month_begin);
                contract.expiration_date = expiration_date_func(month_begin);
                contract.multiplier = multiplier;
                contract.exchange = "TEST";

                contracts.push_back(contract);
            }
        }
    }

    return contracts;
}


struct FutureInfo {
    int sid;
    std::string root_symbol;
    std::string symbol;
    std::chrono::system_clock::time_point start_date;
    std::chrono::system_clock::time_point notice_date;
    std::chrono::system_clock::time_point expiration_date;
    int multiplier;
    std::string exchange;
};

std::vector<FutureInfo> make_commodity_future_info(
        int first_sid,
        std::vector<std::string> root_symbols,
        std::vector<int> years,
        std::map<std::string, int> month_codes = {}, // Default value to be replaced with actual month codes
        int multiplier = 500
) {
    if (month_codes.empty()) {
        // month_codes = CMES_CODE_TO_MONTH; // Replace with actual month codes
    }

    std::vector<std::string> year_strs(years.size());
    std::transform(years.begin(), years.end(), year_strs.begin(), [](int year) { return std::to_string(year); });

    std::vector<FutureInfo> contracts;
    int sid = first_sid;
    for (const auto& root_sym : root_symbols) {
        for (const auto& year_str : year_strs) {
            for (const auto& month_code : month_codes) {
                std::string suffix = month_code.first + year_str.substr(year_str.size() - 2);
                std::chrono::system_clock::time_point month_begin; // Calculate month_begin based on year and month_code.second

                FutureInfo contract;
                contract.sid = sid++;
                contract.root_symbol = root_sym;
                contract.symbol = root_sym + suffix;
                contract.start_date = month_begin - std::chrono::days(365);
                contract.notice_date = month_begin - std::chrono::months(2) + std::chrono::days(19);
                contract.expiration_date = month_begin - std::chrono::months(1) + std::chrono::days(19);
                contract.multiplier = multiplier;
                contract.exchange = "TEST";

                contracts.push_back(contract);
            }
        }
    }

    return contracts;
}