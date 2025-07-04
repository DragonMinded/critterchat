import $ from "jquery";
import { escapeHtml } from "./utils.js";

class Search {
    constructor( eventBus ) {
        this.eventBus = eventBus;
        this.lastSettings = {};
        this.lastSettingsLoaded = false;

        $( '#search' ).on( 'input', (event) => {
            event.preventDefault();

            var searchValue = $('#search').val();
            if (!searchValue) {
                this.populateResults([]);
            } else {
                this.eventBus.emit('searchrooms', searchValue);
            }
        });
    }

    setLastSettings( settings ) {
        this.lastSettings = settings;
        this.lastSettingsLoaded = true;

        if (this.lastSettings.info == "shown") {
            $('div.container > div.info').removeClass('hidden');
        } else {
            $('div.container > div.info').addClass('hidden');
        }
    }

    populateResults( results ) {
        var resultdom = $('div.search > div.results');
        resultdom.empty();

        results.forEach((result) => {
            var id = result.roomid || result.userid;
            var action = "";
            if (result.roomid) {
                action = result.joined ? "jump" : "join";
            } else {
                action = "message";
            }
            var type = result['public'] ? 'room' : 'avatar';

            var html = '<div class="item" id="' + id + '">';
            html    += '  <div class="icon ' + type + '">';
            html    += '    <img src="' + result.icon + '" />';
            html    += '  </div>';
            html    += '  <div class="name-wrapper"><div class="name">' + escapeHtml(result.name) + '</div></div>';
            html    += '  <div class="action-wrapper"><div class="action">' + action + '</div></div>';
            html    += '</div>';
            resultdom.append(html);

            $('div.search > div.results div.item#' + id).on('click', (event) => {
                event.stopPropagation();
                event.stopImmediatePropagation();

                var id = $(event.currentTarget).attr('id')
                this.joinRoom( id );
            });
        });
    }

    joinRoom( id ) {
        $.modal.close();
        $( '#search' ).val("");
        this.populateResults([]);
        this.eventBus.emit('joinroom', id);
    }
}

export { Search };
