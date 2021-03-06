--DROP TRIGGER IF EXISTS image_tagging_state_changes ON Image_Tagging_State;
CREATE TRIGGER image_tagging_state_changes
    BEFORE UPDATE ON Image_Tagging_State
    FOR EACH ROW
        EXECUTE PROCEDURE log_image_tagging_state_changes();
