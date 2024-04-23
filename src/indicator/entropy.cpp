#include <stdlib.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cmath>

constexpr int MKTBUF = 2048;   // Alloc for market info in chunks of this many records
constexpr int NGAPS = 11;      // Number of gaps in analysis


double find_slope(int lookback, std::vector<double>::iterator x) {
    double coef, slope = 0.0, denom = 0.0;

    for (int i = 0; i < lookback; i++) {
        coef = i - 0.5 * (lookback - 1);
        denom += coef * coef;
        slope += coef * *(x++);
    }

    return slope / denom;
}

double atr(int lookback, std::vector<double>::iterator high, std::vector<double>::iterator low, std::vector<double>::iterator close) {
    double term, sum = 0.0;

    for (int i = 0; i < lookback; i++) {
        term = high[i] - low[i];
        if (i) {
            if (high[i] - close[i - 1] > term) {
                term = high[i] - close[i - 1];
            }
            if (close[i - 1] - low[i] > term) {
                term = close[i - 1] - low[i];
            }
        }
        sum += term;
    }

    return sum / lookback;
}

#include <vector>
#include <algorithm>
#include <cmath>

void clean_tails(
        std::vector<double>& raw,      // They are here
        double tail_frac   // Fraction of each tail to be cleaned (0-0.5)
) {
    int n = raw.size();
    double cover = 1.0 - 2.0 * tail_frac;  // Internal fraction preserved

    // Find the interval having desired interior coverage which has the minimum data span
    // Save the raw data, as we have to sort it for this step.
    std::vector<double> work = raw;

    std::sort(work.begin(), work.end());
    int istart = 0;                        // Start search at the beginning
    int istop = static_cast<int>(cover * (n + 1)) - 1; // This gives desired coverage
    if (istop >= n)                     // Happens if careless user has tail=0
        istop = n - 1;

    double best = 1.e60;                // Will be minimum span
    int best_start = 0, best_stop = 0;  // Not needed; shuts up LINT

    while (istop < n) {                    // Test every possible position
        double range = work[istop] - work[istart]; // This is what we minimize
        if (range < best) {
            best = range;
            best_start = istart;
            best_stop = istop;
        }
        ++istart;
        ++istop;
    }

    double minval = work[best_start];  // Value at start of interior interval
    double maxval = work[best_stop];   // And end
    if (maxval <= minval) {      // Rare pathological situation
        maxval *= 1.0 + 1.e-10;
        minval *= 1.0 - 1.e-10;
    }

    // We now have the narrowest coverage.  Clean the tails.
    // We use maxval-minval to keep reasonable scaling.

    double limit = (maxval - minval) * (1.0 - cover);
    double scale = -1.0 / (maxval - minval);

    for (double& val : raw) {
        if (val < minval)         // Left tail
            val = minval - limit * (1.0 - std::exp(scale * (minval - val)));
        else if (val > maxval)   // Right tail
            val = maxval + limit * (1.0 - std::exp(scale * (val - maxval)));
    }
}

#include <vector>
#include <algorithm>

double range_expansion(
        int lookback,   // Window length for computing expansion indicator
        std::vector<double>::iterator x        // Iterator to current price
) {
    auto pptr = x - lookback + 1; // Indicator lookback window starts here
    double recent_high = -1.e60, older_high = -1.e60;
    double recent_low = 1.e60, older_low = 1.e60;

    for (int i = 0; i < lookback / 2; i++) {
        if (*pptr > older_high)
            older_high = *pptr;
        if (*pptr < older_low)
            older_low = *pptr;
        ++pptr;
    }

    while (pptr != x) {
        if (*pptr > recent_high)
            recent_high = *pptr;
        if (*pptr < recent_low)
            recent_low = *pptr;
        ++pptr;
    }

    return (recent_high - recent_low) / (older_high - older_low + 1.e-10);
}

double jump(
        int lookback,     // Window length for computing indicator, greater than 1
        std::vector<double>::iterator x          // Iterator to current price
) {
    double alpha = 2.0 / lookback; // Alpha = 2.0 / (n+1) and n=lookback-1 here
    auto pptr = x - lookback + 1; // Indicator lookback window starts here
    double smoothed = *pptr++;

    for (int i = 1; i < lookback - 1; i++)
        smoothed = alpha * *pptr++ + (1.0 - alpha) * smoothed;

    return *pptr - smoothed;
}

#include <vector>
#include <cmath>
#include <algorithm>

double entropy(
        std::vector<double>& x,  // They are here
        int nbins   // Number of bins, at least 2
) {
    int n = x.size();
    std::vector<int> count(nbins, 0);

    double minval = *std::min_element(x.begin(), x.end());
    double maxval = *std::max_element(x.begin(), x.end());

    double factor = (nbins - 1.e-10) / (maxval - minval + 1.e-60);

    for (double& val : x) {
        int k = static_cast<int>(factor * (val - minval));
        ++count[k];
    }

    double sum = 0.0;
    for (int i = 0; i < nbins; i++) {
        if (count[i]) {
            double p = static_cast<double>(count[i]) / n;
            sum += p * std::log(p);
        }
    }

    return -sum / std::log(static_cast<double>(nbins));
}


void gap_analyze(int n, std::vector<double>::iterator x, double thresh, int ngaps, std::vector<int>& gap_size, std::vector<int>& gap_count) {
    int above_below, new_above_below, count = 1;

    std::fill(gap_count.begin(), gap_count.end(), 0);

    above_below = (*x >= thresh) ? 1 : 0;

    for (int i = 1; i <= n; i++) {
        new_above_below = (i == n) ? 1 - above_below : (*(x + i) >= thresh) ? 1 : 0;
        if (new_above_below == above_below) {
            ++count;
        } else {
            int j = 0;
            for (; j < ngaps - 1; j++) {
                if (count <= gap_size[j])
                    break;
            }
            ++gap_count[j];
            count = 1;
            above_below = new_above_below;
        }
    }
}

int main(int argc, char* argv[]) {
    int i, k, nprices, nind, lookback, bufcnt, itemp, full_date, prior_date, year, month, day;
    int ngaps, version, full_lookback;
    std::vector<int> date, gap_size(NGAPS - 1), gap_count(NGAPS);
    double fractile, trend_min, trend_max, trend_quantile, volatility_min, volatility_max, volatility_quantile;
    std::vector<double> open, high, low, close, trend, trend_sorted, volatility, volatility_sorted;
    std::string line, filename;
    std::ifstream fp;

    if (argc != 6) {
        std::cout << "\nUsage: STATN  Lookback  Fractile  Version  Filename";
        std::cout << "\n  lookback - Lookback for trend and volatility";
        std::cout << "\n  fractile - Fractile (0-1, typically 0.5) for gap analysis";
        std::cout << "\n  version - 0=raw stat; 1=current-prior; >1=current-longer";
        std::cout << "\n  filename - name of market file (YYYYMMDD Price)";
        exit(1);
    }

    lookback = std::stoi(argv[1]);
    fractile = std::stod(argv[2]);
    int nbins = std::stoi(argv[3]);
    version = std::stoi(argv[4]);
    filename = argv[5];

    if (lookback < 2) {
        std::cout << "\n\nLookback must be at least 2";
        return 1;
    }

    if (version == 0)
        full_lookback = lookback;
    else if (version == 1)
        full_lookback = 2 * lookback;
    else if (version > 1)
        full_lookback = version * lookback;
    else {
        std::cout << "\n\nVersion cannot be negative";
        exit(1);
    }

    fp.open(filename, std::ios::in);
    if (!fp.is_open()) {
        std::cout << "\n\nCannot open market history file " << filename;
        return 1;
    }

    date.resize(MKTBUF);
    open.resize(MKTBUF);
    high.resize(MKTBUF);
    low.resize(MKTBUF);
    close.resize(MKTBUF);

    bufcnt = MKTBUF;

    std::cout << "\nReading market file...";

    nprices = 0;
    prior_date = 0;

    while (std::getline(fp, line)) {
        if (line.empty())
            break;

        if (!bufcnt) {
            date.resize(nprices + MKTBUF);
            open.resize(nprices + MKTBUF);
            high.resize(nprices + MKTBUF);
            low.resize(nprices + MKTBUF);
            close.resize(nprices + MKTBUF);
            bufcnt = MKTBUF;
        }

        for (i = 0; i < 8; i++) {
            if (line[i] < '0' || line[i] > '9') {
                std::cout << "\nInvalid date reading line " << nprices + 1 << " of file " << filename;
                return 1;
            }
        }

        full_date = itemp = std::stoi(line.substr(0, 8));
        year = itemp / 10000;
        itemp -= year * 10000;
        month = itemp / 100;
        itemp -= month * 100;
        day = itemp;

        if (month < 1 || month > 12 || day < 1 || day > 31 || year < 1800 || year > 2030) {
            std::cout << "\nERROR... Invalid date " << full_date << " in line " << nprices + 1;
            return 1;
        }

        if (full_date <= prior_date) {
            std::cout << "\nERROR... Date failed to increase in line " << nprices + 1;
            return 1;
        }

        prior_date = full_date;

        date[nprices] = full_date;

        // Parse the open
        size_t pos = line.find_first_of(" \t,", 9);
        open[nprices] = std::stod(line.substr(9, pos - 9));
        if (open[nprices] > 0.0)
            open[nprices] = log(open[nprices]);

        // Parse the high
        pos = line.find_first_not_of(" \t,", pos);
        size_t end = line.find_first_of(" \t,", pos);
        high[nprices] = std::stod(line.substr(pos, end - pos));
        if (high[nprices] > 0.0)
            high[nprices] = log(high[nprices]);

        // Parse the low
        pos = line.find_first_not_of(" \t,", end);
        end = line.find_first_of(" \t,", pos);
        low[nprices] = std::stod(line.substr(pos, end - pos));
        if (low[nprices] > 0.0)
            low[nprices] = log(low[nprices]);

        // Parse the close
        pos = line.find_first_not_of(" \t,", end);
        close[nprices] = std::stod(line.substr(pos));
        if (close[nprices] > 0.0)
            close[nprices] = log(close[nprices]);

        if (low[nprices] > open[nprices] || low[nprices] > close[nprices] ||
            high[nprices] < open[nprices] || high[nprices] < close[nprices]) {
            std::cout << "\nInvalid open/high/low/close reading line " << nprices + 1 << " of file " << filename;
            return 1;
        }

        ++nprices;
        --bufcnt;
    }

    fp.close();

    std::cout << "\nMarket price history read (" << nprices << " lines)";
    std::cout << "\n\nIndicator version " << version;

    // The market data is read.  Initialize for gap analysis

    ngaps = NGAPS;
    k = 1;
    for (i = 0; i < ngaps - 1; i++) {
        gap_size[i] = k;
        k *= 2;
    }

    nind = nprices - full_lookback + 1;

    trend.resize(2 * nind);
    trend_sorted = std::vector<double>(trend.begin() + nind, trend.end());

    trend_min = 1.e60;
    trend_max = -1.e60;
    for (i = 0; i < nind; i++) {
        k = full_lookback - 1 + i;
        if (version == 0) {
            auto it = close.begin();
            std::advance(it, k);
            trend[i] = find_slope(lookback, it);
        }
        else if (version == 1) {
            auto it1 = close.begin();
            std::advance(it1, k);
            auto it2 = close.begin();
            std::advance(it2, k - lookback);
            trend[i] = find_slope(lookback, it1) - find_slope(lookback, it2);
        }
        else {
            auto it1 = close.begin();
            std::advance(it1, k);
            auto it2 = close.begin();
            std::advance(it2, k);
            trend[i] = find_slope(lookback, it1) - find_slope(full_lookback, it2);
        }
        trend_sorted[i] = trend[i];
        if (trend[i] < trend_min)
            trend_min = trend[i];
        if (trend[i] > trend_max)
            trend_max = trend[i];
    }

    std::sort(trend_sorted.begin(), trend_sorted.end());
    k = static_cast<int>(fractile * (nind + 1)) - 1;
    if (k < 0)
        k = 0;
    trend_quantile = trend_sorted[k];

    std::cout << "\n\nTrend  min=" << trend_min << "  max=" << trend_max << "  " << fractile << " quantile=" << trend_quantile;

    std::cout << "\n\nGap analysis for trend with lookback=" << lookback;
    std::cout << "\n  Size   Count";

    gap_analyze(nind, trend.begin(), trend_quantile, ngaps, gap_size, gap_count);

    for (i = 0; i < ngaps; i++) {
        if (i < ngaps - 1)
            std::cout << "\n " << gap_size[i] << " " << gap_count[i];
        else
            std::cout << "\n>" << gap_size[ngaps - 2] << " " << gap_count[i];
    }

    volatility.resize(2 * nind);
    volatility_sorted = std::vector<double>(volatility.begin() + nind, volatility.end());

    volatility_min = 1.e60;
    volatility_max = -1.e60;
    for (i = 0; i < nind; i++) {
        k = full_lookback - 1 + i;
        if (version == 0) {
            auto high_it = high.begin();
            std::advance(high_it, k);
            auto low_it = low.begin();
            std::advance(low_it, k);
            auto close_it = close.begin();
            std::advance(close_it, k);
            volatility[i] = atr(lookback, high_it, low_it, close_it);
        }
        else if (version == 1) {
            auto high_it1 = high.begin();
            std::advance(high_it1, k);
            auto low_it1 = low.begin();
            std::advance(low_it1, k);
            auto close_it1 = close.begin();
            std::advance(close_it1, k);

            auto high_it2 = high.begin();
            std::advance(high_it2, k - lookback);
            auto low_it2 = low.begin();
            std::advance(low_it2, k - lookback);
            auto close_it2 = close.begin();
            std::advance(close_it2, k - lookback);

            volatility[i] = atr(lookback, high_it1, low_it1, close_it1) - atr(lookback, high_it2, low_it2, close_it2);
        }
        else {
            auto high_it1 = high.begin();
            std::advance(high_it1, k);
            auto low_it1 = low.begin();
            std::advance(low_it1, k);
            auto close_it1 = close.begin();
            std::advance(close_it1, k);

            auto high_it2 = high.begin();
            std::advance(high_it2, k);
            auto low_it2 = low.begin();
            std::advance(low_it2, k);
            auto close_it2 = close.begin();
            std::advance(close_it2, k);

            volatility[i] = atr(lookback, high_it1, low_it1, close_it1) - atr(full_lookback, high_it2, low_it2, close_it2);
        }
        volatility_sorted[i] = volatility[i];
        if (volatility[i] < volatility_min)
            volatility_min = volatility[i];
        if (volatility[i] > volatility_max)
            volatility_max = volatility[i];
    }
    std::sort(volatility_sorted.begin(), volatility_sorted.end());
    k = static_cast<int>(fractile * (nind + 1)) - 1;
    if (k < 0)
        k = 0;
    volatility_quantile = volatility_sorted[k];
    std::cout << "\n\nVolatility  min=" << volatility_min << "  max=" << volatility_max << "  " << fractile << " quantile=" << volatility_quantile;
    std::cout << "\n\nGap analysis for volatility with lookback=" << lookback;
    std::cout << "\n  Size   Count";
    gap_analyze(nind, volatility.begin(), volatility_quantile, ngaps, gap_size, gap_count);
    for (i = 0; i < ngaps; i++) {
        if (i < ngaps - 1)
            std::cout << "\n " << gap_size[i] << " " << gap_count[i];
        else
            std::cout << "\n>" << gap_size[ngaps - 2] << " " << gap_count[i];
    }
    return 0;
}