library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cnn_weights_pkg.all;

-- Fixed-point inference engine for the Python network:
-- 100 features -> 32 ReLU values -> 4 class scores -> largest-score class.
-- Supply one Q8 feature on each feature_valid cycle after patch_start.
entity patch_classifier is
    port (
        clk           : in  std_logic;
        rst           : in  std_logic;
        patch_start   : in  std_logic;
        feature_valid : in  std_logic;
        feature_value : in  signed(15 downto 0);
        feature_ready : out std_logic;
        result_valid  : out std_logic;
        result_class  : out unsigned(1 downto 0)
    );
end entity;

architecture rtl of patch_classifier is
    type state_t is (IDLE, LOAD_FEATURES, INIT_OUTPUT, CALC_OUTPUT, CLASSIFY);
    type accum_1_t is array (0 to HIDDEN_COUNT - 1) of signed(39 downto 0);
    type accum_2_t is array (0 to CLASS_COUNT - 1) of signed(39 downto 0);

    signal state       : state_t := IDLE;
    signal feature_idx : natural range 0 to FEATURE_COUNT - 1 := 0;
    signal hidden_idx  : natural range 0 to HIDDEN_COUNT - 1 := 0;
    signal hidden_acc  : accum_1_t := (others => (others => '0'));
    signal output_acc  : accum_2_t := (others => (others => '0'));
begin
    feature_ready <= '1' when state = LOAD_FEATURES else '0';

    process (clk)
        variable product_1 : signed(31 downto 0);
        variable product_2 : signed(31 downto 0);
        variable hidden_q8 : signed(15 downto 0);
        variable best      : natural range 0 to CLASS_COUNT - 1;
    begin
        if rising_edge(clk) then
            result_valid <= '0';

            if rst = '1' then
                state        <= IDLE;
                feature_idx  <= 0;
                hidden_idx   <= 0;
                hidden_acc   <= (others => (others => '0'));
                output_acc   <= (others => (others => '0'));
                result_class <= (others => '0');
            else
                case state is
                    when IDLE =>
                        if patch_start = '1' then
                            -- BIAS_1 is Q12; shifting by 8 aligns it with
                            -- feature(Q8) * weight(Q12), which is Q20.
                            for h in 0 to HIDDEN_COUNT - 1 loop
                                hidden_acc(h) <= shift_left(resize(BIAS_1(h), 40), 8);
                            end loop;
                            feature_idx <= 0;
                            state <= LOAD_FEATURES;
                        end if;

                    when LOAD_FEATURES =>
                        if feature_valid = '1' then
                            for h in 0 to HIDDEN_COUNT - 1 loop
                                product_1 := feature_value * WEIGHTS_1(feature_idx, h);
                                hidden_acc(h) <= hidden_acc(h) + resize(product_1, 40);
                            end loop;

                            if feature_idx = FEATURE_COUNT - 1 then
                                state <= INIT_OUTPUT;
                            else
                                feature_idx <= feature_idx + 1;
                            end if;
                        end if;

                    when INIT_OUTPUT =>
                        -- BIAS_2 is also Q12 and is aligned to Q20 here.
                        for c in 0 to CLASS_COUNT - 1 loop
                            output_acc(c) <= shift_left(resize(BIAS_2(c), 40), 8);
                        end loop;
                        hidden_idx <= 0;
                        state <= CALC_OUTPUT;

                    when CALC_OUTPUT =>
                        -- Convert Q20 hidden sum to Q8; ReLU removes negatives.
                        if hidden_acc(hidden_idx)(39) = '1' then
                            hidden_q8 := (others => '0');
                        else
                            hidden_q8 := resize(shift_right(hidden_acc(hidden_idx), 12), 16);
                        end if;

                        for c in 0 to CLASS_COUNT - 1 loop
                            product_2 := hidden_q8 * WEIGHTS_2(hidden_idx, c);
                            output_acc(c) <= output_acc(c) + resize(product_2, 40);
                        end loop;

                        if hidden_idx = HIDDEN_COUNT - 1 then
                            state <= CLASSIFY;
                        else
                            hidden_idx <= hidden_idx + 1;
                        end if;

                    when CLASSIFY =>
                        best := 0;
                        for c in 1 to CLASS_COUNT - 1 loop
                            if output_acc(c) > output_acc(best) then
                                best := c;
                            end if;
                        end loop;
                        result_class <= to_unsigned(best, result_class'length);
                        result_valid <= '1';
                        state <= IDLE;
                end case;
            end if;
        end if;
    end process;
end architecture;
