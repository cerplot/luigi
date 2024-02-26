

import sys
import warnings

import pytest

if __name__ == '__main__':
    with warnings.catch_warnings():
        warnings.simplefilter("default")
        warnings.filterwarnings(
            "ignore",
            message='(.*)outputs has no custom(.*)',
            category=UserWarning
        )
        sys.exit(pytest.main(sys.argv[1:]))
