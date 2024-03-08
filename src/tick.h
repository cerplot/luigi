#pragma once

enum class Exchange : uint8_t {
    XNSE = 0,   // NSE
    XNAS,       // NASDAQ
    XNYS,       // NYSE
    // Add more exchanges as needed
    ExchangeCount // Keep this last
};

struct Tick {
    struct Update {
        uint16_t BID_PRICE : 1;
        uint16_t BID_SIZE : 1;
        uint16_t ASK_PRICE : 1;
        uint16_t ASK_SIZE : 1;
        uint16_t TRADE_PRICE : 1;
        uint16_t TRADE_SIZE : 1;
        Update() : BID_PRICE(0), BID_SIZE(0), ASK_PRICE(0), ASK_SIZE(0), TRADE_PRICE(0), TRADE_SIZE(0) {}
    } update;

    uint32_t sid;
    Exchange exch;
    uint64_t timestamp;
    float bidPrice;
    float askPrice;
    float tradePrice;
    uint32_t bidSize;
    uint32_t askSize;
    uint32_t tradeSize;
};

