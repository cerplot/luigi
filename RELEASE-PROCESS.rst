


#. Make sure [twine](https://pypi.org/project/twine/) is installed ``pip install twine``.
#. Update version number in `trun/__meta__.py`.
#. Commit, perhaps simply with a commit message like ``Version x.y.z``.
#. Push to GitHub at [spotify/trun](https://github.com/spotify/trun).
#. Clean up previous distributions by executing ``rm -rf dist``
#. Build a source distribution by executing ``python setup.py sdist``
#. Upload to pypi by executing ``twine upload dist/*``
#. Add a tag on github (https://github.com/spotify/trun/releases),
   including a handwritten changelog, possibly inspired from previous notes.
