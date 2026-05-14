"""Regression tests for realistic fire/burn material definitions.

These tests lock in the new material properties set by the fire+explosion
realism pass so future edits don't silently regress. They use the authoritative
`simulation.materials` registry, not the legacy test_helpers PARTICLES mirror.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.materials import get_material, get_all_materials


class TestBurnRealism:
    def test_water_quenches_fire_via_reaction_slot(self):
        """Water must have a reaction with fire producing steam (immediate quench)."""
        water = get_material(2)
        slots = [
            (water.reaction_1_partner, water.reaction_1_product_self, water.reaction_1_prob),
            (water.reaction_2_partner, water.reaction_2_product_self, water.reaction_2_prob),
            (water.reaction_3_partner, water.reaction_3_product_self, water.reaction_3_prob),
        ]
        fire_slots = [s for s in slots if s[0] == 4]  # T_FIRE = 4
        assert fire_slots, "water must react with fire"
        _, prod_self, prob = fire_slots[0]
        assert prod_self == 14, "water + fire -> steam (self becomes steam)"
        assert prob >= 0.99, "water should quench fire deterministically"

    def test_blood_is_not_combustible(self):
        """Blood is mostly water; it should not burn."""
        assert get_material(18).flammability == 0.0

    def test_gas_is_controlled_fuel(self):
        """Gas should ignite intentionally without slowly burning the atmosphere."""
        gas = get_material(10)
        assert 0.3 <= gas.flammability <= 0.5
        assert gas.phase_high_id == 4  # becomes fire
        assert gas.phase_high_temp >= 190
        assert gas.oxygen_requirement >= 0.65

    def test_oil_burns_hotter_and_leaves_ember(self):
        oil = get_material(6)
        assert oil.flammability >= 0.75
        assert oil.phase_high_temp >= 175
        assert oil.oxygen_requirement >= 0.5
        assert oil.burn_to == 58  # heavy smoke/soot residue
        assert oil.default_flame_temp == 96  # TEMP_AMBIENT: oil must not auto-ignite when placed
        assert oil.default_flame_life == 0

    def test_wood_chars_to_coal(self):
        """Wood remains configured for charring rather than straight raw fire."""
        wood = get_material(11)
        assert wood.phase_high_id == 36  # coal
        assert wood.burn_to == 36
        assert wood.default_flame_life > 0

    def test_char_and_soot_materials_exist(self):
        char = get_material(57)
        soot = get_material(58)
        assert char.name == "char"
        assert soot.name == "soot"
        assert 0.2 <= char.flammability <= 0.5
        assert char.burn_to == 25  # ash
        assert soot.flammability == 0.0
        assert soot.phase_low_id == 25  # settles/cools to ash

    def test_plant_embers_first(self):
        plant = get_material(8)
        assert plant.phase_high_id == 33  # ember
        assert plant.burn_to == 33

    def test_sugar_caramelises_to_coal(self):
        sugar = get_material(27)
        assert sugar.phase_high_id == 36
        assert sugar.burn_to == 36

    def test_coal_glows_long_and_emits(self):
        coal = get_material(36)
        assert coal.emissivity >= 0.3
        assert coal.flammability >= 0.5  # coal is combustible
        assert coal.default_flame_temp == 96  # TEMP_AMBIENT: coal must not auto-ignite when placed
        assert coal.default_flame_life == 0
        assert coal.phase_high_id == 33  # -> ember

    def test_napalm_leaves_embers(self):
        napalm = get_material(37)
        assert napalm.burn_to == 33
        assert napalm.emissivity > 0.0

    def test_napalm_has_soot_and_oxygen_reactions(self):
        napalm = get_material(37)
        slots = {
            napalm.reaction_1_partner: napalm.reaction_1_product_self,
            napalm.reaction_2_partner: napalm.reaction_2_product_self,
            napalm.reaction_3_partner: napalm.reaction_3_product_self,
        }
        assert slots[4] == 58  # fire contact can produce soot
        assert slots[32] == 4  # explicit oxygen sustains flame

    def test_glass_melts_to_lava(self):
        glass = get_material(12)
        assert glass.phase_high_id == 9
        assert glass.phase_high_temp <= 250

    def test_metal_melts_to_lava(self):
        metal = get_material(22)
        assert metal.phase_high_id == 9
        assert metal.phase_high_temp >= 0

    def test_ice_actively_cools(self):
        ice = get_material(13)
        assert ice.cooling_rate >= 0.03

    def test_thermite_converts_stone_and_glass(self):
        """Thermite should have reaction slots targeting metal, stone, and glass."""
        therm = get_material(40)
        partners = {
            therm.reaction_1_partner,
            therm.reaction_2_partner,
            therm.reaction_3_partner,
        }
        # T_METAL=22, T_STONE=3, T_GLASS=12
        assert {22, 3, 12}.issubset(partners), f"thermite missing partners, got {partners}"

    def test_fuel_materials_start_at_ambient_temp(self):
        """Fuel materials must start at ambient temp to avoid auto-ignition on placement."""
        from core.constants import TEMP_AMBIENT
        fuel_ids = [6, 8, 10, 36]  # oil, plant, gas, coal
        for mid in fuel_ids:
            mat = get_material(mid)
            assert mat.default_flame_temp == TEMP_AMBIENT, (
                f"{mat.name} default_flame_temp={mat.default_flame_temp} != TEMP_AMBIENT={TEMP_AMBIENT}"
            )
            assert mat.default_flame_life == 0, (
                f"{mat.name} default_flame_life={mat.default_flame_life} != 0"
            )

    def test_all_combustibles_have_ignition_temp(self):
        for mat in get_all_materials().values():
            if mat.flammability > 0 and mat.phase_high_id == 4:
                assert 0 < mat.phase_high_temp, (
                    f"{mat.name} has flamm>0 and phi_h=fire but invalid Th={mat.phase_high_temp}"
                )
