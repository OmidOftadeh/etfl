from etfl.tests.small_model import create_etfl_model

def test_thermo():
    create_etfl_model(has_thermo=True,
                      has_neidhardt=False,
                      n_mu_bins = 4,
                      optimize = False)