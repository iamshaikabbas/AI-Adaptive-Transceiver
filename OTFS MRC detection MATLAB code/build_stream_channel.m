function H = build_stream_channel(chan, NM_phase, mode, len)
% =========================================================================
% BUILD_STREAM_CHANNEL   Sparse time-domain channel matrix acting on an
% arbitrary sample stream:
%
%   r(q) = sum_{l in L_set} h_l(q) * s_in(q-l+1)
%
% with the SAME coefficient convention as Gen_discrete_time_channel.m
% (eq. 16 in [R1]):  h_l(q) = sum_i g_i * z^(k_i*(q-l)),  z = exp(j2pi/NM),
% i.e. the phase is keyed on the absolute INPUT sample index.
%
% INPUTS
%   chan     : channel struct from gen_channel_params_flex
%   NM_phase : Doppler phase period (= N*M of the frame; defines z)
%   mode     : 'linear'   s_in(p)=0 outside [1,len]. Used by ZP-OTFS and
%                          by CP-prepended frames (ODDM / CP-OFDM).
%              'circular' s_in periodic with period len.
%   len      : stream length (default = NM_phase). May exceed NM_phase
%              when a cyclic prefix is prepended; the Doppler phase then
%              keeps advancing on the unwrapped input index p-1.
% =========================================================================

if nargin < 4 || isempty(len), len = NM_phase; end

rows=[]; cols=[]; vals=[];
L_set = unique(chan.delay_taps);
z = exp(1i*2*pi/NM_phase);

switch lower(mode)
    case 'linear'
        for l = (L_set(:)' + 1)
            q_idx = l:len;
            p_idx = q_idx - l + 1;                 % input index (>=1)
            w = zeros(size(q_idx));
            for i = 1:chan.taps
                if chan.delay_taps(i)+1 == l
                    w = w + chan.chan_coef(i)*z.^(chan.Doppler_taps(i)*(p_idx-1));
                end
            end
            rows = [rows, q_idx]; cols = [cols, p_idx]; vals = [vals, w]; %#ok<AGROW>
        end

    case 'circular'
        qv = (0:len-1);
        for l = (L_set(:)')
            p_idx = mod(qv - l, len);               % wrapped input index
            w = zeros(size(qv));
            for i = 1:chan.taps
                if chan.delay_taps(i) == l
                    w = w + chan.chan_coef(i)*z.^(chan.Doppler_taps(i)*p_idx);
                end
            end
            rows = [rows, qv+1]; cols = [cols, p_idx+1]; vals = [vals, w]; %#ok<AGROW>
        end

    otherwise
        error('build_stream_channel: unknown mode "%s" (linear|circular).', mode);
end

H = sparse(rows, cols, vals, len, len);
end
