import pytest

from edisgo.io import ding0_import
from edisgo.network.components import Generator, Load, Switch
from edisgo.network.grids import LVGrid
from edisgo.network.topology import Topology


class TestGrids:
    @classmethod
    def setup_class(self):
        self.topology = Topology()
        ding0_import.import_ding0_grid(pytest.ding0_test_network_path, self)

    def test_mv_grid(self):
        """Test MVGrid class getter, setter, methods"""

        mv_grid = self.topology.mv_grid

        # test getter
        assert mv_grid.id == 1
        assert mv_grid.nominal_voltage == 20
        lv_grids = list(mv_grid.lv_grids)
        assert len(lv_grids) == 10
        assert isinstance(lv_grids[0], LVGrid)

        assert len(mv_grid.buses_df.index) == 31
        assert "Bus_BranchTee_MVGrid_1_7" in mv_grid.buses_df.index

        assert len(mv_grid.generators_df.index) == 8
        assert "Generator_slack" not in mv_grid.generators_df.index
        assert "Generator_1" in mv_grid.generators_df.index
        gen_list = list(mv_grid.generators)
        assert isinstance(gen_list[0], Generator)

        assert len(mv_grid.loads_df.index) == 0

        assert len(mv_grid.transformers_df.index) == 1
        assert "MVStation_1_transformer_1" in mv_grid.transformers_df.index

        assert len(mv_grid.switch_disconnectors_df.index) == 2
        assert "circuit_breaker_1" in mv_grid.switch_disconnectors_df.index
        switch_list = list(mv_grid.switch_disconnectors)
        assert isinstance(switch_list[0], Switch)
        assert len(switch_list) == 2

        assert sorted(mv_grid.weather_cells) == [1122074, 1122075]
        assert mv_grid.peak_generation_capacity == 19.025
        assert mv_grid.peak_generation_capacity_per_technology["solar"] == 4.6
        assert mv_grid.p_set == 0.0

    def test_lv_grid(self):
        """Test LVGrid class getter, setter, methods"""
        lv_grid = self.topology.get_lv_grid(3)

        assert isinstance(lv_grid, LVGrid)
        assert lv_grid.id == 3
        assert lv_grid.nominal_voltage == 0.4

        assert len(lv_grid.buses_df) == 9
        assert "Bus_BranchTee_LVGrid_3_2" in lv_grid.buses_df.index

        assert len(lv_grid.generators_df.index) == 0
        gen_list = list(lv_grid.generators)
        assert len(gen_list) == 0

        assert len(lv_grid.loads_df.index) == 4
        assert "Load_residential_LVGrid_3_2" in lv_grid.loads_df.index
        load_list = list(lv_grid.loads)
        assert isinstance(load_list[0], Load)
        assert len(load_list) == 4

        assert len(lv_grid.transformers_df.index) == 1
        assert "LVStation_3_transformer_1" in lv_grid.transformers_df.index

        assert len(lv_grid.switch_disconnectors_df.index) == 0
        switch_list = list(lv_grid.switch_disconnectors)
        assert len(switch_list) == 0

        assert sorted(lv_grid.weather_cells) == []
        assert lv_grid.peak_generation_capacity == 0
        assert lv_grid.peak_generation_capacity_per_technology.empty
        assert lv_grid.p_set == 0.054627
        assert lv_grid.p_set_per_sector["agricultural"] == 0.051
