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