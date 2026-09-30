from conftest import existence_def

from core.mp_declare_model import MPDeclareModel


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


def test_empty_model():
    model = MPDeclareModel.build([])
    assert model.constraints == ()
    assert model.begin_index == {}
    assert model.finish_index == {}
    assert model.ordering_constraints == ()
