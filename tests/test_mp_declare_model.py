from conftest import existence_def

from core.mp_declare_model import MPDeclareModel


def test_activity_index():
    model = MPDeclareModel.build(
        [
            existence_def("add", "test1"),
            existence_def("delete", "test2"),
            existence_def("add", "test3"),
        ]
    )
    assert model.activity_index["add"] == (0, 2)
    assert model.activity_index["delete"] == (1,)


def test_empty_model():
    model = MPDeclareModel.build([])
    assert model.constraints == ()
    assert model.activity_index == {}
