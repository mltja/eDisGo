import logging
import math

from abc import ABC, abstractmethod
from math import acos, tan

from shapely.geometry import Point

from edisgo.io.electromobility_import import determine_grid_connection_capacity
from edisgo.tools.geo import find_nearest_bus

logger = logging.getLogger(__name__)


class BasicComponent(ABC):
    """
    Generic component

    Can be initialized with EDisGo object or Topology object. In case of
    Topology object component time series attributes currently will raise an
    error.

    """

    def __init__(self, **kwargs):
        self._id = kwargs.get("id", None)
        self._edisgo_obj = kwargs.get("edisgo_obj", None)
        self._topology = kwargs.get("topology", None)
        if self._topology is None and self._edisgo_obj is not None:
            self._topology = self._edisgo_obj.topology

    @property
    def id(self):
        """
        Unique identifier of component as used in component dataframes in
        :class:`~.network.topology.Topology`.

        Returns
        --------
        :obj:`str`
            Unique identifier of component.

        """
        return self._id

    @property
    def edisgo_obj(self):
        """
        EDisGo container

        Returns
        --------
        :class:`~.EDisGo`

        """
        return self._edisgo_obj

    @property
    def topology(self):
        """
        Network topology container

        Returns
        --------
        :class:`~.network.topology.Topology`

        """
        return self._topology

    @property
    def voltage_level(self):
        """
        Voltage level the component is connected to ('mv' or 'lv').

        Returns
        --------
        :obj:`str`
            Voltage level. Returns 'lv' if component connected to the low
            voltage and 'mv' if component is connected to the medium voltage.

        """
        return "lv" if self.grid.nominal_voltage < 1 else "mv"

    @property
    @abstractmethod
    def grid(self):
        """
        Grid component is in.

        Returns
        --------
        :class:`~.network.components.Grid`
            Grid component is in.

        """

    def __repr__(self):
        return "_".join([self.__class__.__name__, str(self._id)])


class Component(BasicComponent):
    """
    Generic component for all components that can be considered nodes,
    e.g. generators and loads.

    """

    @property
    @abstractmethod
    def _network_component_df(self):
        """
        Dataframe in :class:`~.network.topology.Topology` containing all components
        of same type, e.g. for loads this is
        :attr:`~.network.topology.Topology.loads_df`.

        """

    @property
    def bus(self):
        """
        Bus component is connected to.

        Parameters
        -----------
        bus : :obj:`str`
            ID of bus to connect component to.

        Returns
        --------
        :obj:`str`
            Bus component is connected to.

        """
        return self._network_component_df.at[self.id, "bus"]

    @bus.setter
    def bus(self, bus):
        self._set_bus(bus)

    def _set_bus(self, bus):
        raise NotImplementedError

    @property
    def grid(self):
        """
        Grid component is in.

        Returns
        --------
        :class:`~.network.components.Grid`
            Grid component is in.

        """
        grid = self.topology.buses_df.loc[
            self._network_component_df.loc[self.id, "bus"],
            ["mv_grid_id", "lv_grid_id"],
        ]
        if math.isnan(grid.lv_grid_id):
            return self.topology.mv_grid
        else:
            return self.topology._grids["LVGrid_{}".format(int(grid.lv_grid_id))]

    @property
    def geom(self):
        """
        Geo location of component.

        Returns
        --------
        :shapely:`Point`

        """
        [x, y] = self.topology.buses_df.loc[
            self._network_component_df.loc[self.id, "bus"], ["x", "y"]
        ]
        if math.isnan(x) or math.isnan(y):
            return None
        else:
            return Point(x, y)

    def __repr__(self):
        return "_".join([self.__class__.__name__, str(self._id)])


class Load(Component):
    """
    Load object

    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def _network_component_df(self):
        """
        Dataframe in :class:`~.network.topology.Topology` containing all loads.

        For loads this is :attr:`~.network.topology.Topology.loads_df`.

        Returns
        --------
        :pandas:`pandas.DataFrame<dataframe>`
            See :attr:`~.network.topology.Topology.loads_df` for more information.

        """
        return self.topology.loads_df

    @property
    def p_set(self):
        """
        Peak load in MW.

        Parameters
        -----------
        p_set : :obj:`float`
            Peak load in MW.

        Returns
        --------
        :obj:`float`
            Peak load in MW.

        """
        return self.topology.loads_df.at[self.id, "p_set"]

    @p_set.setter
    def p_set(self, p_set):
        self.topology._loads_df.at[self.id, "p_set"] = float(p_set)

    @property
    def annual_consumption(self):
        """
        Annual consumption of load in MWh.

        Parameters
        -----------
        annual_consumption : :obj:`float`
            Annual consumption in MWh.

        Returns
        --------
        :obj:`float`
            Annual consumption of load in MWh.

        """
        return self.topology.loads_df.at[self.id, "annual_consumption"]

    @annual_consumption.setter
    def annual_consumption(self, annual_consumption):
        self.topology._loads_df.at[self.id, "annual_consumption"] = annual_consumption

    @property
    def sector(self):
        """
        Sector load is associated with.

        The sector is e.g. used to assign load time series to a load using the
        demandlib. The following four sectors are considered:
        'agricultural', 'retail', 'residential', 'industrial'.

        Parameters
        -----------
        sector : :obj:`str`

        Returns
        --------
        :obj:`str`
            Load sector

        #ToDo: Maybe return 'not specified' in case sector is None?

        """
        return self.topology.loads_df.at[self.id, "sector"]

    @sector.setter
    def sector(self, sector):
        # ToDo: Maybe perform type check before setting it.
        self.topology._loads_df.at[self.id, "sector"] = sector

    @property
    def active_power_timeseries(self):
        """
        Active power time series of load in MW.

        Returns
        --------
        :pandas:`pandas.Series<Series>`
            Active power time series of load in MW.

        """
        return self.edisgo_obj.timeseries.loads_active_power.loc[:, self.id]

    @property
    def reactive_power_timeseries(self):
        """
        Reactive power time series of load in Mvar.

        Returns
        --------
        :pandas:`pandas.Series<Series>`
            Reactive power time series of load in Mvar.

        """
        return self.edisgo_obj.timeseries.loads_reactive_power.loc[:, self.id]

    def _set_bus(self, bus):
        # check if bus is valid
        if bus in self.topology.buses_df.index:
            self.topology._loads_df.at[self.id, "bus"] = bus
            # reset topology
            self._grid = None
        else:
            raise AttributeError("Given bus ID does not exist.")


class Generator(Component):
    """
    Generator object

    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def _network_component_df(self):
        """
        Dataframe in :class:`~.network.topology.Topology` containing generators.

        For generators this is :attr:`~.network.topology.Topology.generators_df`.

        Returns
        --------
        :pandas:`pandas.DataFrame<dataframe>`
            See :attr:`~.network.topology.Topology.generators_df` for more
            information.

        """
        return self.topology.generators_df

    @property
    def nominal_power(self):
        """
        Nominal power of generator in MW.

        Parameters
        -----------
        nominal_power : :obj:`float`
            Nominal power of generator in MW.

        Returns
        --------
        :obj:`float`
            Nominal power of generator in MW.

        """
        # TODO: Should this change the time series as well?
        #  (same for loads, and type setter...)
        return self.topology.generators_df.at[self.id, "p_nom"]

    @nominal_power.setter
    def nominal_power(self, nominal_power):
        # ToDo: Maybe perform type check before setting it.
        self.topology._generators_df.at[self.id, "p_nom"] = nominal_power

    @property
    def type(self):
        """
        Technology type of generator (e.g. 'solar').

        Parameters
        -----------
        type : :obj:`str`

        Returns
        --------
        :obj:`str`
            Technology type

        #ToDo: Maybe return 'not specified' in case type is None?

        """
        return self.topology.generators_df.at[self.id, "type"]

    @type.setter
    def type(self, type):
        # ToDo: Maybe perform type check before setting it.
        self.topology._generators_df.at[self.id, "type"] = type

    @property
    def subtype(self):
        """
        Technology subtype of generator (e.g. 'solar_roof_mounted').

        Parameters
        -----------
        subtype : :obj:`str`

        Returns
        --------
        :obj:`str`
            Technology subtype

        #ToDo: Maybe return 'not specified' in case subtype is None?

        """
        return self.topology.generators_df.at[self.id, "subtype"]

    @subtype.setter
    def subtype(self, subtype):
        self.topology._generators_df.at[self.id, "subtype"] = subtype

    @property
    def active_power_timeseries(self):
        """
        Active power time series of generator in MW.

        Returns
        --------
        :pandas:`pandas.Series<Series>`
            Active power time series of generator in MW.

        """
        return self.edisgo_obj.timeseries.generators_active_power.loc[:, self.id]

    @property
    def reactive_power_timeseries(self):
        """
        Reactive power time series of generator in Mvar.

        Returns
        --------
        :pandas:`pandas.Series<Series>`
            Reactive power time series of generator in Mvar.

        """
        return self.edisgo_obj.timeseries.generators_reactive_power.loc[:, self.id]

    @property
    def weather_cell_id(self):
        """
        Weather cell ID of generator.

        The weather cell ID is only used to obtain generator feed-in time
        series for solar and wind generators.

        Parameters
        -----------
        weather_cell_id : int
            Weather cell ID of generator.

        Returns
        --------
        :obj:`int`
            Weather cell ID of generator.

        """
        return self.topology.generators_df.at[self.id, "weather_cell_id"]

    @weather_cell_id.setter
    def weather_cell_id(self, weather_cell_id):
        self.topology._generators_df.at[self.id, "weather_cell_id"] = weather_cell_id

    def _set_bus(self, bus):
        # check if bus is valid
        if bus in self.topology.buses_df.index:
            self.topology._generators_df.at[self.id, "bus"] = bus
            # reset topology
            self._grid = None
        else:
            raise AttributeError("Given bus ID does not exist.")


class Storage(Component):
    """
    Storage object

    ToDo: adapt to refactored code!

    Describes a single storage instance in the eDisGo network. Includes technical
    parameters such as :attr:`Storage.efficiency_in` or
    :attr:`Storage.standing_loss` as well as its time series of operation
    :meth:`Storage.timeseries`.

    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        raise NotImplementedError

        self._timeseries = kwargs.get("timeseries", None)
        self._nominal_power = kwargs.get("nominal_power", None)
        self._power_factor = kwargs.get("power_factor", None)
        self._reactive_power_mode = kwargs.get("reactive_power_mode", None)

        self._max_hours = kwargs.get("max_hours", None)
        self._soc_initial = kwargs.get("soc_initial", None)
        self._efficiency_in = kwargs.get("efficiency_in", None)
        self._efficiency_out = kwargs.get("efficiency_out", None)
        self._standing_loss = kwargs.get("standing_loss", None)
        self._operation = kwargs.get("operation", None)
        self._reactive_power_mode = kwargs.get("reactive_power_mode", None)
        self._q_sign = None

    @property
    def _network_component_df(self):
        """
        Dataframe in :class:`~.network.topology.Topology` containing all switches.

        For switches this is :attr:`~.network.topology.Topology.switches_df`.

        Returns
        --------
        :pandas:`pandas.DataFrame<dataframe>`
            See :attr:`~.network.topology.Topology.switches_df` for more
            information.

        """
        return self.topology.switches_df

    @property
    def timeseries(self):
        """
        Time series of storage operation

        Parameters
        ----------
        ts : :pandas:`pandas.DataFrame<dataframe>`
            DataFrame containing active power the storage is charged (negative)
            and discharged (positive) with (on the topology side) in kW in column
            'p' and reactive power in kvar in column 'q'. When 'q' is positive,
            reactive power is supplied (behaving as a capacitor) and when 'q'
            is negative reactive power is consumed (behaving as an inductor).

        Returns
        -------
        :pandas:`pandas.DataFrame<dataframe>`
            See parameter `timeseries`.

        """
        # check if time series for reactive power is given, otherwise
        # calculate it
        if "q" in self._timeseries.columns:
            return self._timeseries
        else:
            self._timeseries["q"] = (
                abs(self._timeseries.p) * self.q_sign * tan(acos(self.power_factor))
            )
            return self._timeseries.loc[self.grid.edisgo_obj.timeseries.timeindex, :]

    @property
    def nominal_power(self):
        """
        Nominal charging and discharging power of storage instance in kW.

        Returns
        -------
        float
            Storage nominal power

        """
        return self._nominal_power

    @property
    def max_hours(self):
        """
        Maximum state of charge capacity in terms of hours at full discharging
        power `nominal_power`.

        Returns
        -------
        float
            Hours storage can be discharged for at nominal power

        """
        return self._max_hours

    @property
    def nominal_capacity(self):
        """
        Nominal storage capacity in kWh.

        Returns
        -------
        float
            Storage nominal capacity

        """
        return self._max_hours * self._nominal_power

    @property
    def soc_initial(self):
        """Initial state of charge in kWh.

        Returns
        -------
        float
            Initial state of charge

        """
        return self._soc_initial

    @property
    def efficiency_in(self):
        """Storage charging efficiency in per unit.

        Returns
        -------
        float
            Charging efficiency in range of 0..1

        """
        return self._efficiency_in

    @property
    def efficiency_out(self):
        """Storage discharging efficiency in per unit.

        Returns
        -------
        float
            Discharging efficiency in range of 0..1

        """
        return self._efficiency_out

    @property
    def standing_loss(self):
        """Standing losses of storage in %/100 / h

        Losses relative to SoC per hour. The unit is pu (%/100%). Hence, it
        ranges from 0..1.

        Returns
        -------
        float
            Standing losses in pu.

        """
        return self._standing_loss

    @property
    def operation(self):
        """
        Storage operation definition

        Returns
        -------
        :obj:`str`

        """
        self._operation

    # @property
    # def power_factor(self):
    #     """
    #     Power factor of storage
    #
    #     If power factor is not set it is retrieved from the topology config
    #     object depending on the topology level the storage is in.
    #
    #     Returns
    #     --------
    #     :obj:`float` : Power factor
    #         Ratio of real power to apparent power.
    #
    #     """
    #     if self._power_factor is None:
    #         if isinstance(self.topology, MVGrid):
    #             self._power_factor = self.topology.topology.config[
    #                 'reactive_power_factor']['mv_storage']
    #         elif isinstance(self.topology, LVGrid):
    #             self._power_factor = self.topology.topology.config[
    #                 'reactive_power_factor']['lv_storage']
    #     return self._power_factor
    #
    # @power_factor.setter
    # def power_factor(self, power_factor):
    #     self._power_factor = power_factor

    # @property
    # def reactive_power_mode(self):
    #     """
    #     Power factor mode of storage.
    #
    #     If the power factor is set, then it is necessary to know whether
    #     it is leading or lagging. In other words this information is necessary
    #     to make the storage behave in an inductive or capacitive manner.
    #     Essentially this changes the sign of the reactive power Q.
    #
    #     The convention used here in a storage is that:
    #     - when `reactive_power_mode` is 'capacitive' then Q is positive
    #     - when `reactive_power_mode` is 'inductive' then Q is negative
    #
    #     In the case that this attribute is not set, it is retrieved from the
    #     topology config object depending on the voltage level the storage
    #     is in.
    #
    #     Returns
    #     -------
    #     :obj: `str` : Power factor mode
    #         Either 'inductive' or 'capacitive'
    #
    #     """
    #     if self._reactive_power_mode is None:
    #         if isinstance(self.topology, MVGrid):
    #             self._reactive_power_mode = self.topology.topology.config[
    #                 'reactive_power_mode']['mv_storage']
    #         elif isinstance(self.topology, LVGrid):
    #             self._reactive_power_mode = self.topology.topology.config[
    #                 'reactive_power_mode']['lv_storage']
    #
    #     return self._reactive_power_mode

    # @reactive_power_mode.setter
    # def reactive_power_mode(self, reactive_power_mode):
    #     """
    #     Set the power factor mode of the generator.
    #     Should be either 'inductive' or 'capacitive'
    #     """
    #     self._reactive_power_mode = reactive_power_mode

    @property
    def q_sign(self):
        """
        Get the sign reactive power based on the
        :attr: `_reactive_power_mode`

        Returns
        -------
        :obj: `int` : +1 or -1
        """
        if self.reactive_power_mode.lower() == "inductive":
            return -1
        elif self.reactive_power_mode.lower() == "capacitive":
            return 1
        else:
            raise ValueError(
                "Unknown value {} in reactive_power_mode".format(
                    self.reactive_power_mode
                )
            )

    def __repr__(self):
        return str(self._id)


class Switch(BasicComponent):
    """
    Switch object

    Switches are for example medium voltage disconnecting points (points
    where MV rings are split under normal operation conditions). They are
    represented as branches and can have two states: 'open' or 'closed'. When
    the switch is open the branch it is represented by connects some bus and
    the bus specified in `bus_open`. When it is closed bus `bus_open` is
    substitued by the bus specified in `bus_closed`.


    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._state = kwargs.get("state", None)

    @property
    def _network_component_df(self):
        """
        Dataframe in :class:`~.network.topology.Topology` containing all switches.

        For switches this is :attr:`~.network.topology.Topology.switches_df`.

        Returns
        --------
        :pandas:`pandas.DataFrame<dataframe>`
            See :attr:`~.network.topology.Topology.switches_df` for more
            information.

        """
        return self.topology.switches_df

    @property
    def type(self):
        """
        Type of switch.

        So far edisgo only considers switch disconnectors.

        Parameters
        -----------
        type : :obj:`str`
            Type of switch.

        Returns
        --------
        :obj:`str`
            Type of switch.

        """
        return self.topology.switches_df.at[self.id, "type_info"]

    @type.setter
    def type(self, type):
        self.topology._switches_df.at[self.id, "type_info"] = type

    @property
    def bus_open(self):
        """
        Bus ID of bus the switch is 'connected' to when state is 'open'.

        As switches are represented as branches they connect two buses.
        `bus_open` specifies the bus the branch is connected to in the open
        state.

        Returns
        --------
        :obj:`str`
            Bus in 'open' state.

        """
        return self.topology.switches_df.at[self.id, "bus_open"]

    @property
    def bus_closed(self):
        """
        Bus ID of bus the switch is 'connected' to when state is 'closed'.

        As switches are represented as branches they connect two buses.
        `bus_closed` specifies the bus the branch is connected to in the closed
        state.

        Returns
        --------
        :obj:`str`
            Bus in 'closed' state.

        """
        return self.topology.switches_df.at[self.id, "bus_closed"]

    @property
    def state(self):
        """
        State of switch (open or closed).

        Returns
        -------
        str
            State of switch: 'open' or 'closed'.

        """
        if self._state is None:
            col_closed = self._get_bus_column(self.bus_closed)
            col_open = self._get_bus_column(self.bus_open)
            if col_closed is None and col_open is not None:
                self._state = "open"
            elif col_closed is not None and col_open is None:
                self._state = "closed"
            else:
                raise AttributeError("State of switch could not be determined.")
        return self._state

    @property
    def branch(self):
        """
        Branch the switch is represented by.

        Returns
        -------
        str
            Branch the switch is represented by.

        """
        return self.topology.switches_df.at[self.id, "branch"]

    @property
    def grid(self):
        """
        Grid switch is in.

        Returns
        --------
        :class:`~.topology.components.Grid`
            Grid switch is in.

        """
        grid = self.topology.buses_df.loc[self.bus_closed, ["mv_grid_id", "lv_grid_id"]]
        if math.isnan(grid.lv_grid_id):
            return self.topology.mv_grid
        else:
            return self.topology._grids["LVGrid_{}".format(int(grid.lv_grid_id))]

    def open(self):
        """
        Open switch.

        """
        if self.state != "open":
            self._state = "open"
            col = self._get_bus_column(self.bus_closed)
            if col is not None:
                self.topology.lines_df.at[self.branch, col] = self.bus_open
            else:
                raise AttributeError(
                    "Could not open switch {}. Specified branch {} of switch "
                    "has no bus {}. Please check the switch.".format(
                        self.id, self.branch, self.bus_closed
                    )
                )

    def close(self):
        """
        Close switch.

        """
        if self.state != "closed":
            self._state = "closed"
            col = self._get_bus_column(self.bus_open)
            if col is not None:
                self.topology.lines_df.at[self.branch, col] = self.bus_closed
            else:
                raise AttributeError(
                    "Could not close switch {}. Specified branch {} of switch "
                    "has no bus {}. Please check the switch.".format(
                        self.id, self.branch, self.bus_closed
                    )
                )

    def _get_bus_column(self, bus):
        """
        Returns column name of lines_df given bus is in.

        """
        if bus == self.topology.lines_df.at[self.branch, "bus0"]:
            col = "bus0"
        elif bus == self.topology.lines_df.at[self.branch, "bus1"]:
            col = "bus1"
        else:
            return None
        return col


class PotentialChargingParks(BasicComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def voltage_level(self):
        """
        Voltage level the component is connected to ('mv' or 'lv').

        Returns
        --------
        :obj:`str`
            Voltage level. Returns 'lv' if component connected to the low
            voltage and 'mv' if component is connected to the medium voltage.

        """
        try:
            return "lv" if self.grid.nominal_voltage < 1 else "mv"
        except Exception:
            return None

    @property
    def grid(self):
        """
        Grid component is in.

        Returns
        --------
        :class:`~.network.components.Grid`
            Grid component is in.

        """
        try:
            bus = self.topology.charging_points_df.at[self.edisgo_id, "bus"]
            lv_grid_id = self.topology.buses_df.at[bus, "lv_grid_id"]
            if math.isnan(lv_grid_id):
                return self.topology.mv_grid
            else:
                return self.topology._grids[f"LVGrid_{int(lv_grid_id)}"]
        except Exception:
            return None

    @property
    def ags(self):
        """
        8-digit AGS (Amtlicher Gemeindeschlüssel, eng. Community Identification
        Number) number the potential charging park is in. Number is given as
        :obj:`int` and leading zeros are therefore missing.

        Returns
        --------
        :obj:`int`
            AGS number

        """
        return self._edisgo_obj.electromobility.grid_connections_gdf.at[self._id, "ags"]

    @property
    def use_case(self):
        """
        Charging use case (home, work, public or hpc) of the potential
        charging park.

        Returns
        --------
        :obj:`str`
            Charging use case

        """
        return self._edisgo_obj.electromobility.grid_connections_gdf.at[
            self._id, "use_case"
        ]

    @property
    def designated_charging_point_capacity(self):
        """
        Total gross designated charging park capacity.
        This is not necessarily equal to the connection rating.

        Returns
        --------
        :obj:`float`
            Total gross designated charging park capacity

        """
        return round(
            self.charging_processes_df.groupby("charging_point_id")
            .max()
            .netto_charging_capacity.sum()
            / self._edisgo_obj.electromobility.eta_charging_points,
            1,
        )

    @property
    def user_centric_weight(self):
        """
        User centric weight of the potential charging park
        determined by `SimBEV <https://github.com/rl-institut/simbev>`_.

        Returns
        --------
        :obj:`float`
            User centric weight

        """
        return self._edisgo_obj.electromobility.grid_connections_gdf.at[
            self._id, "user_centric_weight"
        ]

    @property
    def geometry(self):
        """
        Location of the potential charging park as
        :shapely:`Shapely Point object<points>`.

        Returns
        --------
        :shapely:`Shapely Point object<points>`.
            Location of the potential charging park

        """
        return self._edisgo_obj.electromobility.grid_connections_gdf.at[
            self._id, "geometry"
        ]

    @property
    def nearest_substation(self):
        """
        Determines the nearest LV Grid, substation and distance.

        Returns
        --------
        :obj:`dict`
            :obj:`int`
                LV Grid ID
            :obj:`str`
                ID of the nearest substation
            :obj:`float`
                Distance to nearest substation

        """
        substations = self._topology.buses_df.loc[self._topology.transformers_df.bus1]

        nearest_substation, distance = find_nearest_bus(self.geometry, substations)

        lv_grid_id = int(self._topology.buses_df.at[nearest_substation, "lv_grid_id"])

        return {
            "lv_grid_id": lv_grid_id,
            "nearest_substation": nearest_substation,
            "distance": distance,
        }

    @property
    def edisgo_id(self):
        try:
            return self._edisgo_obj.electromobility.integrated_charging_parks_df.at[
                self.id, "edisgo_id"
            ]
        except Exception:
            return None

    @property
    def charging_processes_df(self):
        """
        Determines designated charging processes for the potential charging
        park.

        Returns
        --------
        :pandas:`pandas.DataFrame<DataFrame>`
            DataFrame with AGS, car ID, trip destination, charging use case
            (private or public), netto charging capacity, charging demand,
            charge start, charge end, grid connection point and charging point
            ID.

        """
        return self._edisgo_obj.electromobility.charging_processes_df.loc[
            self._edisgo_obj.electromobility.charging_processes_df.charging_park_id
            == self._id
        ]

    @property
    def grid_connection_capacity(self):
        if self.use_case == "hpc":
            return self.designated_charging_point_capacity / 10**3
        else:
            return determine_grid_connection_capacity(
                self.designated_charging_point_capacity / 10**3
            )

    @property
    def within_grid(self):
        """
        Deetermines if the potential charging park lays within the grid
        district.
        """
        return self._edisgo_obj.topology.grid_district["geom"].contains(self.geometry)

    @property
    def _last_charging_process_and_netto_charging_capacity_per_charging_point(self):
        return (
            self.charging_processes_df[
                ["charging_point_id", "park_end", "netto_charging_capacity"]
            ]
            .groupby(by="charging_point_id")
            .max()
        )

    @property
    def _load_and_generator_capacity_weight(self, **kwargs):
        """
        Determines grid centric weight regarding load and generator capacity
        in LV Grid.

        Returns
        --------
        :obj:`float`
            Grid centric weight regarding load and generator capacity in LV
            Grid
        """
        generators_weight_factor = kwargs.get("generators_weight_factor", 1 / 2)
        loads_weight_factor = kwargs.get("loads_weight_factor", 1 / 2)

        weights = (loads_weight_factor, generators_weight_factor)

        if not round(sum(weights), 3) == 1:
            f = 1 / sum(weights)
            generators_weight_factor *= f
            loads_weight_factor *= f

        generators_weight_value = self._topology.lv_grids_df.at[
            self.nearest_substation["lv_grid_id"], "generators_weight"
        ]

        loads_weight_value = self._topology.lv_grids_df.at[
            self.nearest_substation["lv_grid_id"], "loads_weight"
        ]

        return (
            generators_weight_value * generators_weight_factor
            + loads_weight_value * loads_weight_factor
        )
