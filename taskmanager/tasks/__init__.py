import os
import glob

# grab all the python files in the current directory and throw them into __all__
# we'll iterate over them later to grab class instances, i suppose
__all__ = [ os.path.basename(f)[:-3] for f in glob.glob(os.path.dirname(__file__)+"/*.py")]
