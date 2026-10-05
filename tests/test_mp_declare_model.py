from conftest import existence_def, init_def, precedence_def

from governancekit.engine.mp_declare_model import MPDeclareModel


def test_finish_index():
    model = MPDeclareModel.build(
        [
            existence_def("add", "test1"),
            existence_def("delete", "test2"),
            existence_def("add", "test3"),
        ]
    )
    assert model.finish_index["add"] == (0, 2)
    assert model.finish_index["delete"] == (1,)


def test_constraint_groups():
    model = MPDeclareModel.build(
        [
            precedence_def("delete", "authorize", "p", "src"),
            existence_def("close_ticket", "e"),
            init_def("login", "i"),
        ]
    )
    # Precedence can block both of its activities
    assert model.begin_index == {"delete": (0,), "authorize": (0,)}
    # Existence never blocks, but must hear about completions
    assert model.finish_index == {"delete": (0,), "authorize": (0,), "close_ticket": (1,)}
    # Init concerns every activity, so it is in neither index
    assert model.ordering_constraints == (2,)


def test_empty_model():
    model = MPDeclareModel.build([])
    assert model.constraints == ()
    assert model.begin_index == {}
    assert model.finish_index == {}
    assert model.ordering_constraints == ()
